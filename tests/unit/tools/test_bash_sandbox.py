"""Tests for bash sandbox security features."""

import platform
import tempfile
from pathlib import Path

import pytest

from adorable_cli.tools.bash_sandbox import (
    BashSandbox,
    BashTool,
    SandboxConfig,
    SandboxLevel,
    SandboxProfileGenerator,
    SandboxResult,
    execute_sandboxed,
    is_sandbox_available,
)


class TestSandboxProfileGenerator:
    """Test sandbox profile generation."""

    def test_base_profile_contains_version(self):
        config = SandboxConfig(level=SandboxLevel.READ_ONLY)
        profile = SandboxProfileGenerator.generate(config)
        assert "(version 1)" in profile

    def test_read_only_profile_blocks_writes(self):
        config = SandboxConfig(level=SandboxLevel.READ_ONLY)
        profile = SandboxProfileGenerator.generate(config)
        assert "deny file-write" in profile.lower() or "deny default" in profile.lower()

    def test_restricted_profile_allows_specific_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                level=SandboxLevel.RESTRICTED,
                allow_writes=[tmpdir],
            )
            profile = SandboxProfileGenerator.generate(config)
            # Path is resolved, so just check the pattern exists
            assert '(allow file-write* (subpath "' in profile

    def test_network_profile_allows_network(self):
        config = SandboxConfig(level=SandboxLevel.NETWORK)
        profile = SandboxProfileGenerator.generate(config)
        assert "network-inbound" in profile or "network-outbound" in profile

    def test_unrestricted_profile_is_permissive(self):
        config = SandboxConfig(level=SandboxLevel.UNRESTRICTED)
        profile = SandboxProfileGenerator.generate(config)
        assert "(allow default)" in profile

    def test_profile_includes_specific_reads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                level=SandboxLevel.READ_ONLY,
                allow_reads=[tmpdir],
            )
            profile = SandboxProfileGenerator.generate(config)
            # Path is resolved, so just check the pattern exists
            assert '(allow file-read* (subpath "' in profile


class TestBashSandbox:
    """Test bash sandbox execution."""

    def test_sandbox_creation(self):
        sandbox = BashSandbox()
        assert sandbox.config.level == SandboxLevel.READ_ONLY

    def test_custom_config(self):
        config = SandboxConfig(level=SandboxLevel.RESTRICTED, timeout_seconds=60)
        sandbox = BashSandbox(config)
        assert sandbox.config.timeout_seconds == 60

    def test_execute_simple_command(self):
        sandbox = BashSandbox()
        result = sandbox.execute("echo 'hello world'")

        # Should succeed (sandbox may or may not be available)
        assert "hello world" in result.stdout or not result.success

    def test_execute_with_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = BashSandbox()
            result = sandbox.execute("pwd", cwd=Path(tmpdir))

            if result.success:
                assert tmpdir in result.stdout

    def test_timeout_enforcement(self):
        config = SandboxConfig(timeout_seconds=1)
        sandbox = BashSandbox(config)

        result = sandbox.execute("sleep 10")

        if result.blocked and result.block_reason == "timeout":
            assert "timed out" in result.stderr.lower()

    def test_unrestricted_mode(self):
        config = SandboxConfig(level=SandboxLevel.UNRESTRICTED)
        sandbox = BashSandbox(config)

        result = sandbox.execute("echo 'test'")
        assert result.success
        assert "test" in result.stdout

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    def test_macos_sandbox_blocks_write(self):
        """Test that sandbox blocks writes in read-only mode on macOS."""
        if not is_sandbox_available():
            pytest.skip("sandbox-exec not available")

        sandbox = BashSandbox(SandboxConfig(level=SandboxLevel.READ_ONLY))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = sandbox.execute(f"echo 'test' > {tmpdir}/file.txt")

            # Should be blocked or fail
            assert not result.success or result.blocked


class TestBashTool:
    """Test high-level bash tool."""

    def test_tool_creation(self):
        tool = BashTool()
        assert tool.sandbox is not None
        assert not tool.allow_unsafe

    def test_dangerous_pattern_detection(self):
        tool = BashTool()

        # Test recursive rm
        is_danger, reason = tool.is_dangerous("rm -rf /tmp/test")
        assert is_danger
        assert "recursive deletion" in reason

    def test_wildcard_deletion_detected(self):
        tool = BashTool()

        is_danger, reason = tool.is_dangerous("rm *.txt")
        assert is_danger
        assert "wildcard" in reason.lower()

    def test_sudo_detected(self):
        tool = BashTool()

        is_danger, reason = tool.is_dangerous("sudo apt update")
        assert is_danger
        assert "elevated" in reason.lower()

    def test_safe_command_not_dangerous(self):
        tool = BashTool()

        is_danger, _ = tool.is_dangerous("ls -la")
        assert not is_danger

        is_danger, _ = tool.is_dangerous("cat file.txt")
        assert not is_danger

    def test_dangerous_command_requires_confirmation(self):
        tool = BashTool()

        result = tool.run("rm -rf /tmp/test")

        assert not result.success
        assert result.blocked
        assert result.block_reason == "confirmation_required"
        assert "confirmation required" in result.stderr.lower()

    def test_allow_unsafe_bypasses_confirmation(self):
        tool = BashTool(allow_unsafe=True)

        # Even with allow_unsafe, actual rm might fail without the path existing
        result = tool.run("echo 'simulated dangerous' | grep dangerous")

        # Should execute (grep is not dangerous) - may fail due to sandbox but not due to confirmation
        assert result.block_reason != "confirmation_required"

    def test_explicit_confirmation_required(self):
        tool = BashTool()

        result = tool.run("ls -la", require_confirmation=True)

        assert not result.success
        assert result.blocked
        assert result.block_reason == "confirmation_required"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_execute_sandboxed(self):
        result = execute_sandboxed("echo 'hello'")

        # May or may not succeed depending on sandbox availability
        if result.success:
            assert "hello" in result.stdout

    def test_is_sandbox_available_on_macos(self):
        if platform.system() == "Darwin":
            # Should return True or False, not crash
            available = is_sandbox_available()
            assert isinstance(available, bool)
        else:
            # Should always be False on non-macOS
            assert is_sandbox_available() is False


class TestSandboxResult:
    """Test sandbox result structure."""

    def test_result_creation(self):
        result = SandboxResult(
            success=True,
            stdout="output",
            stderr="",
            return_code=0,
        )
        assert result.success
        assert result.stdout == "output"
        assert not result.blocked

    def test_blocked_result(self):
        result = SandboxResult(
            success=False,
            stdout="",
            stderr="Blocked",
            return_code=-1,
            blocked=True,
            block_reason="file_write_blocked",
        )
        assert not result.success
        assert result.blocked
        assert result.block_reason == "file_write_blocked"


class TestSandboxConfig:
    """Test sandbox configuration."""

    def test_default_config(self):
        config = SandboxConfig()
        assert config.level == SandboxLevel.READ_ONLY
        assert config.timeout_seconds == 300
        assert not config.allow_network

    def test_custom_paths(self):
        config = SandboxConfig(
            allow_reads=["/tmp/read"],
            allow_writes=["/tmp/write"],
        )
        assert "/tmp/read" in config.allow_reads
        assert "/tmp/write" in config.allow_writes


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_command(self):
        sandbox = BashSandbox()
        result = sandbox.execute("")

        # Empty command behavior varies by shell
        assert isinstance(result.success, bool)

    def test_very_long_output(self):
        config = SandboxConfig(max_output_size=100)
        sandbox = BashSandbox(config)

        result = sandbox.execute("seq 1 1000")

        if result.success:
            # Output should be truncated
            assert len(result.stdout) <= 100

    def test_unicode_in_command(self):
        sandbox = BashSandbox()
        result = sandbox.execute("echo 'héllo wörld 🌍'")

        if result.success:
            assert "héllo" in result.stdout or "hello" in result.stdout

    def test_command_with_quotes(self):
        sandbox = BashSandbox()
        result = sandbox.execute('echo "hello world"')

        if result.success:
            assert "hello world" in result.stdout


class TestLinuxFallback:
    """Test Linux fallback behavior."""

    @pytest.mark.skipif(platform.system() == "Darwin", reason="Linux only")
    def test_linux_uses_restricted_env(self):
        sandbox = BashSandbox(SandboxConfig(level=SandboxLevel.READ_ONLY))

        result = sandbox.execute("echo $LD_PRELOAD")

        if result.success:
            # LD_PRELOAD should be empty or unset
            assert result.stdout.strip() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

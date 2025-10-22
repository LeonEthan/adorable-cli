from adorable_cli.tools import create_secure_shell_tools


def main():
    tools = create_secure_shell_tools()

    print("=== Allowed: ls ===")
    out = tools.run_shell_command("ls")
    print(out)

    print("\n=== Allowed: grep (no pipes) ===")
    out = tools.run_shell_command("grep -n Adorable README.md")
    print(out)

    print("\n=== Blocked: pipe usage ===")
    out = tools.run_shell_command("cat README.md | grep Adorable")
    print(out)

    print("\n=== Blocked: curl ===")
    out = tools.run_shell_command("curl https://example.com")
    print(out)

    print("\n=== Blocked: rm -rf ===")
    out = tools.run_shell_command("rm -rf /")
    print(out)

    print("\n=== Blocked: redirection ===")
    out = tools.run_shell_command("ls > out.txt")
    print(out)


if __name__ == "__main__":
    main()

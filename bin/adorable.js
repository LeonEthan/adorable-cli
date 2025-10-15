#!/usr/bin/env node
const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const platformPkgs = {
  "darwin:arm64": "adorable-cli-darwin-arm64",
  "darwin:x64": "adorable-cli-darwin-x64",
  "linux:x64": "adorable-cli-linux-x64",
  "win32:x64": "adorable-cli-win32-x64",
};

function resolveModulePackageRoot(pkg) {
  try {
    const pkgJson = require.resolve(`${pkg}/package.json`);
    return path.dirname(pkgJson);
  } catch {
    return null;
  }
}

function resolveLocalPackageRoot(pkg) {
  const localRoot = path.join(__dirname, "..", "npm", pkg);
  return fs.existsSync(localRoot) ? localRoot : null;
}

function resolveBinary() {
  const key = `${process.platform}:${process.arch}`;
  const pkg = platformPkgs[key];
  if (!pkg) return null;

  const pkgRoot = resolveModulePackageRoot(pkg) || resolveLocalPackageRoot(pkg);
  if (!pkgRoot) return null;

  const exe = process.platform === "win32"
    ? path.join(pkgRoot, "vendor", "adorable.exe")
    : path.join(pkgRoot, "vendor", "adorable");
  return fs.existsSync(exe) ? exe : null;
}

(function main() {
  const key = `${process.platform}:${process.arch}`;
  if (key === "linux:arm64") {
    console.error("[adorable-cli] 当前不支持 Linux arm64。请使用 Linux x64、macOS 或 Windows，或参考 README.md 使用 Docker/源码运行方式。");
    process.exit(1);
  }
  const bin = resolveBinary();
  if (!bin) {
    console.error("[adorable-cli] 未找到平台二进制。请确认已安装对应子包，或在源码模式下将二进制置于 npm/ 对应子包的 vendor/ 下。");
    process.exit(1);
  }
  const args = process.argv.slice(2);
  const res = spawnSync(bin, args, { stdio: "inherit" });
  process.exit(res.status ?? 1);
})();
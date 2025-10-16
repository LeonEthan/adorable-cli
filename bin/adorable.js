#!/usr/bin/env node
const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const platformPkgs = {
  "darwin:arm64": "@loenethan/adorable-cli-darwin-arm64",
  "darwin:x64": "@loenethan/adorable-cli-darwin-x64",
  "linux:x64": "@loenethan/adorable-cli-linux-x64",
  "win32:x64": "@loenethan/adorable-cli-win32-x64",
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

  // 支持两种布局：
  // 1) 单文件：vendor/adorable (或 Windows 的 vendor/adorable.exe)
  // 2) 目录（onedir）：vendor/adorable/adorable (或 Windows 的 vendor/adorable/adorable.exe)
  const singleFile = process.platform === "win32"
    ? path.join(pkgRoot, "vendor", "adorable.exe")
    : path.join(pkgRoot, "vendor", "adorable");

  if (fs.existsSync(singleFile)) {
    // 如果是目录，继续向下解析真实可执行文件
    try {
      const stat = fs.statSync(singleFile);
      if (stat.isDirectory()) {
        const nested = process.platform === "win32"
          ? path.join(singleFile, "adorable.exe")
          : path.join(singleFile, "adorable");
        return fs.existsSync(nested) ? nested : null;
      }
    } catch {}
    return singleFile;
  }

  // 兼容部分打包产物将目录命名为 vendor/adorable/ 并在其下提供可执行
  const dirPath = path.join(pkgRoot, "vendor", "adorable");
  if (fs.existsSync(dirPath)) {
    const nested = process.platform === "win32"
      ? path.join(dirPath, "adorable.exe")
      : path.join(dirPath, "adorable");
    return fs.existsSync(nested) ? nested : null;
  }

  return null;
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
  // 调试：设置 ADOR_DEBUG=1 时打印使用的二进制路径
  if (process.env.ADOR_DEBUG === "1") {
    console.error("[adorable-cli] Using binary:", bin);
  }
  const args = process.argv.slice(2);
  const res = spawnSync(bin, args, { stdio: "inherit" });
  process.exit(res.status ?? 1);
})();
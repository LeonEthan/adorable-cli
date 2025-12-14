# Changelog

## [0.2.5](https://github.com/LeonEthan/adorable-cli/compare/v0.2.4...v0.2.5) (2025-12-14)


### Bug Fixes

* **ci:** pin actions/create-github-app-token to v1 tag ([7a1648a](https://github.com/LeonEthan/adorable-cli/commit/7a1648a15cb9fc5c33e7f129ac5d089ee9aee5b2))
* **ci:** pin actions/create-github-app-token to v1 tag ([b982b80](https://github.com/LeonEthan/adorable-cli/commit/b982b803a5b0232b66b1b92529804f52c2ca03df))
* **ci:** use GitHub App token for release-please ([7cb6480](https://github.com/LeonEthan/adorable-cli/commit/7cb6480a46265d4ab0ad14e55006fe275a640f0d))
* **ci:** use GitHub App token for release-please ([59549a5](https://github.com/LeonEthan/adorable-cli/commit/59549a59a0b09158e1f445f4117ac96ffa299a80))

## [0.2.4](https://github.com/LeonEthan/adorable-cli/compare/v0.2.3...v0.2.4) (2025-12-13)


### Bug Fixes

* **ci:** use GITHUB_TOKEN for release-please to fix 403 error ([7c5dd92](https://github.com/LeonEthan/adorable-cli/commit/7c5dd9205b0a553ee094e2bfd2f1c407639a4438))
* **ci:** use GITHUB_TOKEN instead of failing MY_RELEASE_TOKEN ([c2229c6](https://github.com/LeonEthan/adorable-cli/commit/c2229c68675f2dfc7bf374242a13abb169ab417f))


### Documentation

* update README with correct tools and env vars ([9c64a79](https://github.com/LeonEthan/adorable-cli/commit/9c64a79c2a307ff553f8c5cf72b1f02fa92f9279))
* update README with correct tools and env vars ([d4ea06d](https://github.com/LeonEthan/adorable-cli/commit/d4ea06d6abe45be36b29fbd68db127b935a310ac))

## [0.2.3](https://github.com/LeonEthan/adorable-cli/compare/v0.2.2...v0.2.3) (2025-12-12)


### Features

* Implement interleaved thinking and refactor configuration ([d8ffae7](https://github.com/LeonEthan/adorable-cli/commit/d8ffae7bdce36acb49e7fad2617cac8f43fcdabb))
* Implement interleaved thinking and refactor configuration ([a4b78a8](https://github.com/LeonEthan/adorable-cli/commit/a4b78a80afe0bc1a9fa701efc4c297ec6d8eabba))

## [0.2.2](https://github.com/LeonEthan/adorable-cli/compare/v0.2.1...v0.2.2) (2025-12-06)


### Documentation

* rename da abbreviation to ador ([2bdc12c](https://github.com/LeonEthan/adorable-cli/commit/2bdc12ca94f252e6c803e718bec40d1e77da191d))
* rename da abbreviation to ador ([9ae79c0](https://github.com/LeonEthan/adorable-cli/commit/9ae79c0181b5ab4ab0bba0bb3fd04f32ac426a60))

## [0.2.1](https://github.com/LeonEthan/adorable-cli/compare/v0.1.13...v0.2.1) (2025-12-05)


### Features

* **cli:** integrate Typer commands and unify Rich theming\n\n- Add Typer app with commands: chat, config, mode, version\n- Global options: --model, --base-url, --api-key, --fast-model, --confirm-mode, --debug, --debug-level, --plain\n- Introduce Rich Theme keys and apply consistently across panels and messages\n- Use Rich Syntax for Python/shell previews; add language detection for save_file\n- Consolidate footer via StreamRenderer.render_footer and remove legacy render_stream\n- Remove legacy print_help and manual CLI parsing\n- Panelize enhanced input help; consistent tool-call headers\n\nPreserves interactive behavior while improving discoverability and visual consistency. ([11f1440](https://github.com/LeonEthan/adorable-cli/commit/11f1440e0df1fbf84855e9dce60334550ef4e5d1))
* **prompt:** advance prompt; upgrade agno to 2.2.8; add max tool history ([aa19a23](https://github.com/LeonEthan/adorable-cli/commit/aa19a23eb0ea62d1081d4ee214cf2b10bffc44c0))


### Bug Fixes

* add missing release-please manifest and trigger v0.2.1 ([6f84c74](https://github.com/LeonEthan/adorable-cli/commit/6f84c74a12ee0c45cb68825c36eebc66909646e1))
* **ci:** add write permissions to release-please workflow ([bcc3e52](https://github.com/LeonEthan/adorable-cli/commit/bcc3e52be4ee68d591af7344a27178c4f3345125))
* **ci:** add write permissions to release-please workflow ([023111e](https://github.com/LeonEthan/adorable-cli/commit/023111e84ba8df0f237dd41e91019c93f47cd526))


### Documentation

* **readme:** add Typer CLI commands and global options (EN/CN)\n\n- Document chat, config, mode, version commands\n- Add global flags: --model, --fast-model, --base-url, --api-key, --confirm-mode, --debug, --debug-level, --plain\n- Add examples and enhanced input tip (help-input)\n- Keep module invocation and entrypoints references consistent ([0f8d107](https://github.com/LeonEthan/adorable-cli/commit/0f8d1071c4673a8d3d1c8ff60a78185508edcb2c))
* **readme:** replace remaining Chinese with English and fix language badge\n\n- Translate Session Summary Integration section to English\n- Update language badge to ZH-CN Chinese in EN README ([ddf1d9a](https://github.com/LeonEthan/adorable-cli/commit/ddf1d9a691b549faa75a9eedfe86a80dc673b31a))
* **readme:** revert language badge to 🇨🇳 中文 on EN readme ([f986ec1](https://github.com/LeonEthan/adorable-cli/commit/f986ec15baacc002ad9ce4b0fa901307626eab0e))


### Miscellaneous Chores

* add missing release-please-manifest.json ([0fe590b](https://github.com/LeonEthan/adorable-cli/commit/0fe590bacab4f2b43d6563d6dd267097e4a83c18))
* revert project name to adorable-cli ([f40334e](https://github.com/LeonEthan/adorable-cli/commit/f40334e1264a78ea942e2d3e327a4dabda5b83db))
* switch to python release-type for better commit handling ([3338505](https://github.com/LeonEthan/adorable-cli/commit/33385058bdb86f7252bca3058543922878aedd69))
* trigger release v0.2.1 ([9c17011](https://github.com/LeonEthan/adorable-cli/commit/9c17011d21b032bd0d60d914e6b7b874795ea4cd))

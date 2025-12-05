# Changelog

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

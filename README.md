# U.GG Simplified Chinese

Simplified Chinese UI patch for the standalone U.GG 2.3.3 desktop app on Windows.

## Requirements

- Windows and Python 3.10 or later.
- U.GG 2.3.3 installed under `%LOCALAPPDATA%\Programs\U.GG`.
- Original `app.asar` SHA-256: `c2077b77ab85fa6d7fc02604cc2b56840a67cdea4415a4de504001b05fb3e581`.

## Install

1. Download and extract the ZIP from [Releases](https://github.com/zhui-zi/ugg-zh-cn/releases/latest).
2. Exit U.GG completely from its system tray menu.
3. Run `install.cmd`.
4. Start U.GG normally.

## Restore

Exit U.GG completely, then run `restore.cmd` from the extracted package.

The original archive is preserved at `%LOCALAPPDATA%\Programs\U.GG\resources\app.asar.ugg-zh-cn.original`.

## Coverage and compatibility

Desktop navigation, common settings and statistics, and Deadlock pages and overlay controls are localized. Proper names, item descriptions, and community content can retain their source language. New online interface text may require updated translations.

Desktop Chinese display has been confirmed. In-game overlay display has not been verified.

The installer checks the original archive and patch assets, refuses to replace files while U.GG is running, and protects modified installations during restoration. Application updates can replace the patch; other archives require a compatible release.

The package applies translations to an existing U.GG installation. It does not start or stop applications, change game files, or modify account data.

# pending-questions: a question pane for Claude Code

pending-questions is a Claude Code plugin (a mod) that keeps the questions Claude asked you from scrolling out of sight. After each response it extracts the questions that wait for your answer, registers them in a pane beside the chat, and sends your answer back to the session as a prompt. Questions are stored in files, so they survive a session exit or a crash.

The pane in auto mode, captured from a terminal session and trimmed. Question text stays in the language of the conversation; the interface is in English.

```
Mode: auto [ Switch to manual ] [ Rescan last response ]
[ q2. 로그 형식은 json 과 text 중 어느 쪽으로 할까요? ]
로그를 어떤 형식으로 기록할지 정해야 합니다. 응답에는 권장 형식이
명시되어 있지 않습니다.
Recommended: json
Auto mode leaves this open: the response states no recommendation.
[ Not a question ]
[auto] q1. 배포 대상은 staging 과 production 중 어디로 할까요? →
staging
```

## Features

- **Automatic registration.** A small model reads each response and registers the questions and decisions that need your answer.
- **Three question kinds.** Single choice opens a dialog. Multiple choice shows checkable rows in the pane with the recommended options already checked. Free-form questions show an input with a recommended draft.
- **Automatic closing.** A question closes as `[resolved]` when the conversation or a tool result settles it. The model must quote the evidence, and the plugin checks that quote against the conversation.
- **Manual and auto modes.** Auto mode answers only the questions whose recommendation appears in the response. Everything else stays open for you. History shows how each question was handled.
- **Corrections.** `Not a question` closes a wrong entry, `Reopen` restores a wrongly closed one, and `Rescan last response` reads the last response again with a stronger model.
- **Crash recovery.** Questions, unread responses and undelivered answers are written to disk first, so a restart continues where the session stopped.
- **Other sessions.** The pane lists open questions in other sessions with the same working directory, with the `claude --resume` command for each.

## Install

At the Claude Code prompt:

```
/plugin install pending-questions --marketplace hwanyong/pending-questions
```

In a shell:

```
claude plugin install pending-questions --marketplace hwanyong/pending-questions
```

Plugin changes apply after Claude Code restarts. To update or remove it:

```
claude plugin update pending-questions@pending-questions
claude plugin uninstall pending-questions@pending-questions
```

## Usage

The pane opens when a session starts. `/questions` opens it again after you close it.

Press `ctrl+x` then `Tab` to move keyboard focus to the pane, `Tab` to move between controls, and `Enter` to press one. The same `ctrl+x` then `Tab` returns focus to the prompt.

| Question kind | How you answer |
|---|---|
| Single choice | Press the question to open a dialog. Five or more options are split into pages with `More options` |
| Multiple choice | Toggle the rows, optionally type an addition, then press `Send` |
| Free-form | Edit the recommended draft and press `Enter` |

History marks each closed question:

| Mark | Meaning |
|---|---|
| `[manual]` | You answered it |
| `[auto]` | Auto mode sent the recommendation stated in the response |
| `[resolved]` | The conversation or a tool result settled it |
| `[dismissed]` | You pressed `Not a question` |

### Auto mode

Auto mode answers without showing you the question, so it has three limits:

- It answers only when the response itself recommends an answer. The extraction model must quote that recommendation, and the plugin checks the quote against the response. A question without one stays open, with a note in the pane.
- A question Claude asks through the `AskUserQuestion` tool is answered only when every question in the call has an option marked `(Recommended)`. Otherwise the dialog opens.
- After 5 automatic answers in a row it pauses until you type a prompt or answer a question.

## How it works

1. When a turn ends, the response is written to a file as unread.
2. The `haiku` model extracts new questions and resolved ones. `Rescan last response` uses the `sonnet` model.
3. Your answer is written to the file, then submitted to the session as a prompt. On restart, undelivered answers are compared with the conversation record so none is sent twice.

Each session writes to two files in turn, `<sessionId>.0.json` and `<sessionId>.1.json`, in `~/.claude/pending-questions/`. A write interrupted halfway leaves the previous version intact. After each write, `hooks/flush.pl` asks the operating system to commit the file and its folder to disk (`F_FULLFSYNC` on macOS, `fsync` elsewhere). If that fails, the plugin shows a toast and keeps the written file.

## Data and cost

- Each response, the user prompt and a part of the turn's tool output are sent to the extraction model through your Claude Code session. Extraction uses your account's usage on every response that ends a turn. The amount has not been measured.
- Question files are plain JSON in `~/.claude/pending-questions/`. They contain question text, answers and unread responses.

## Limitations

- Extraction is done by a model, so it can miss a question, register something that is not one, or close one wrongly. The corrections above undo these; they do not prevent them.
- Auto mode trusts the quoted sentence. A sentence in the response that the model wrongly cites as a recommendation passes the check.
- Recovery was tested with `kill -9`. A real power loss or reboot has not been tested. Whether data survives also depends on the drive honoring the flush.
- Tested on macOS with Claude Code 2.1.312 in a terminal. Not tested: Linux, Windows, mobile (where free-form questions fall back to a dialog with `Decide later`), the desktop app and `claude --bg`.
- `hooks/flush.pl` needs `perl` on the `PATH`. Without it, every write shows a toast and the files are still written.

## Development

```
claude --plugin-dir .
npx -y -p typescript tsc -p .
claude plugin validate .
```

Design decisions, measured engine constraints and test records are in [docs/handoff.md](docs/handoff.md) (Korean). Keep `--debug-file` logs outside the plugin folder: the symlink it creates there can stop `/questions` when the folder is on an SMB share.

## License

[MIT](LICENSE)

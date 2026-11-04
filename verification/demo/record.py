"""README 의 화면을 실제 Claude Code 세션에서 녹화한다.

사용법: DEMO_ROOT=<빈 폴더> <venv>/bin/python verification/demo/record.py [장면 이름 ...]
venv 에는 pillow 와 fonttools 를 설치한다. tmux 와 로그인된 claude 가 필요하다.

세션은 DEMO_ROOT/home 을 HOME 으로 쓰므로 사용자의 설정 · 플러그인 · 질문 파일을 읽지 않는다.
로그인은 키체인 폴더만 링크해 가져온다. 응답은 --append-system-prompt-file 의 대본으로 고정한다.
플러그인 · 추출 모델 · dialog · 답 전달은 실제로 동작한다.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import render

REPO = Path(__file__).resolve().parents[2]
OUTPUT = REPO / 'docs' / 'images'
ROOT = Path(os.environ['DEMO_ROOT'])
HOME = ROOT / 'home'
PROJECT = HOME / 'acme-api'
QUESTION_FILES = HOME / '.claude' / 'pending-questions'
SCRIPT_FILE = HOME / 'scene-script.txt'
WIDTH = 120
HEIGHT = 36
SOCKET = 'pq-demo'
TMUX_CONF = """set -g mouse on
set -g status off
set -g focus-events on
set -g default-terminal "xterm-256color"
set -ga terminal-overrides ",*:Tc"
"""

PREAMBLE = """You are in a scripted screen recording. Reply with exactly the scripted text and nothing else. Use no tools unless the script says so. Never add a question that is not in the script.
When a message contains "Answer", reply with exactly one line: Noted.
"""


def prepare_home():
    (HOME / 'bin').mkdir(parents=True, exist_ok=True)
    (HOME / 'Library').mkdir(exist_ok=True)
    PROJECT.mkdir(exist_ok=True)
    real_library = Path.home() / 'Library'
    for name in ('Keychains', 'Preferences'):
        link = HOME / 'Library' / name
        if not link.is_symlink():
            link.symlink_to(real_library / name)
    state = HOME / '.claude.json'
    if not state.exists():
        state.write_text(json.dumps({
            'hasCompletedOnboarding': True,
            'theme': 'dark',
            'projects': {str(PROJECT): {'hasTrustDialogAccepted': True}},
        }))
    wrapper = HOME / 'bin' / 'claude'
    wrapper.write_text(
        '#!/bin/zsh\n'
        f'exec {shutil.which("claude")} --setting-sources project --plugin-dir {REPO} --strict-mcp-config '
        f'--model haiku --permission-mode acceptEdits --append-system-prompt-file {SCRIPT_FILE} "$@"\n'
    )
    wrapper.chmod(0o755)
    (ROOT / 'tmux.conf').write_text(TMUX_CONF)


def tmux(*args, check=True):
    return subprocess.run(
        ['tmux', '-L', SOCKET, *args], check=check, capture_output=True, text=True,
    ).stdout


class Take:
    def __init__(self, name, title, script):
        self.name = name
        self.title = title
        self.frames = []
        self.stills = []
        self.events = []
        self.forbidden = set()
        self.caption = ''
        self.key_label = ''
        self.mark = None
        self.fonts = render.Fonts()
        SCRIPT_FILE.write_text(PREAMBLE + script)
        shutil.rmtree(QUESTION_FILES, ignore_errors=True)
        tmux('kill-server', check=False)
        env = {
            'HOME': str(HOME),
            'PATH': f'{HOME / "bin"}:{os.environ["PATH"]}',
            'LANG': 'en_US.UTF-8',
            'LC_ALL': 'en_US.UTF-8',
            'COLORTERM': 'truecolor',
            'DISABLE_AUTOUPDATER': '1',
            'PS1': '$ ',
            'CLAUDE_CONFIG_DIR': '',
        }
        exports = ' '.join(f"{key}='{value}'" for key, value in env.items() if value != '')
        tmux(
            '-f', str(ROOT / 'tmux.conf'), 'new-session', '-d', '-s', 'demo',
            '-x', str(WIDTH), '-y', str(HEIGHT), '-c', str(PROJECT),
            f"env -u CLAUDE_CONFIG_DIR {exports} zsh -f",
        )
        time.sleep(0.5)
        tmux('send-keys', '-t', 'demo', 'C-l')
        time.sleep(0.3)

    def ansi(self):
        return tmux('capture-pane', '-e', '-p', '-N', '-t', 'demo')

    def text(self):
        return tmux('capture-pane', '-p', '-t', 'demo')

    def rows(self, ansi=None):
        return render.mask_private(render.parse_screen(ansi or self.ansi(), WIDTH, HEIGHT))

    def image(self, ansi=None, mark=None, mark_width=3):
        rows = self.rows(ansi)
        self.forbidden.update(render.forbidden_text(rows))
        return render.draw_frame(
            rows, WIDTH, HEIGHT, self.fonts, self.title,
            self.caption, self.key_label, mark, mark_width,
        )

    def say(self, caption):
        self.caption = caption
        self.events.append(caption)

    def shoot(self, duration):
        self.frames.append((self.image(), duration))

    def hold(self, duration, mark=None):
        """마지막 화면을 멈춰 보여 준다. mark 는 (첫 행 정규식, 마지막 행 정규식 또는 None) 이고 테두리를 두 단계로 키운다."""
        time.sleep(0.2)
        ansi = self.ansi()
        if mark is None:
            self.frames.append((self.image(ansi), duration))
            return
        self.frames.append((self.image(ansi, mark, 2), 140))
        self.frames.append((self.image(ansi, mark, 5), 140))
        self.frames.append((self.image(ansi, mark, 3), max(duration - 280, 100)))

    def still(self, name, mark=None):
        self.stills.append((name, self.image(mark=mark)))

    def type_text(self, text):
        """한 번에 두 글자씩 넣고 프레임을 남긴다."""
        for start in range(0, len(text), 2):
            tmux('send-keys', '-t', 'demo', '-l', '--', text[start:start + 2])
            time.sleep(0.03)
            self.shoot(70)

    def press(self, key, label, pause=0.5, duration=450):
        self.key_label = label
        tmux('send-keys', '-t', 'demo', key)
        time.sleep(pause)
        self.shoot(duration)

    def chord(self, label, *keys):
        self.key_label = label
        for key in keys:
            tmux('send-keys', '-t', 'demo', key)
            time.sleep(0.4)
        time.sleep(0.4)
        self.shoot(500)

    def enter_prompt(self, text):
        self.key_label = ''
        self.type_text(text)
        time.sleep(0.3)
        self.press('Enter', 'Enter', pause=0.4)
        self.key_label = ''

    def wait_for(self, pattern, timeout=120):
        """pattern 이 화면에 나올 때까지 기다린다. 기다리는 동안의 프레임은 앞 두 장과 마지막 장만 남긴다."""
        started = time.time()
        seen = []
        while time.time() - started < timeout:
            ansi = self.ansi()
            if not seen or seen[-1] != ansi:
                seen.append(ansi)
            if re.search(pattern, self.text()):
                kept = seen[:2] + seen[-1:] if len(seen) > 2 else seen
                for screen in kept:
                    self.frames.append((self.image(screen), 300))
                self.events.append(f'waited {time.time() - started:.0f}s for {pattern}')
                return
            time.sleep(1)
        print(self.text())
        raise TimeoutError(f'{self.name}: {pattern}')

    def wait_idle(self, pattern):
        """응답이 끝날 때까지 기다린 뒤 추출에 걸리는 시간을 더 기다리지 않는다."""
        self.wait_for(pattern)

    def focus(self, pattern, limit=40):
        """pattern 이 반전으로 그려질 때까지 Tab 을 누른다."""
        for _ in range(limit):
            if re.search(pattern, render.reversed_text(self.rows())):
                return
            self.press('Tab', 'Tab', pause=0.35, duration=260)
        print(self.text())
        raise TimeoutError(f'{self.name}: focus {pattern}')

    def start_claude(self, arguments=''):
        self.key_label = ''
        tmux('send-keys', '-t', 'demo', '-l', f'claude {arguments}'.strip())
        tmux('send-keys', '-t', 'demo', 'Enter')
        self.wait_for(r'❯\s')
        time.sleep(4)

    def open_pane(self):
        tmux('send-keys', '-t', 'demo', '-l', '/questions')
        time.sleep(0.5)
        tmux('send-keys', '-t', 'demo', 'Enter')
        self.wait_for(r'Switch to (auto|manual)')
        time.sleep(0.5)

    def claude_pid(self):
        pane_pid = tmux('list-panes', '-t', 'demo', '-F', '#{pane_pid}').strip()
        children = subprocess.run(['pgrep', '-P', pane_pid], capture_output=True, text=True).stdout.split()
        return int(children[0])

    def session_id(self):
        names = sorted(QUESTION_FILES.glob('*.json'), key=lambda path: path.stat().st_mtime)
        return names[-1].name.split('.')[0]

    def finish(self):
        if self.forbidden:
            raise TimeoutError(f'{self.name}: frames contain {sorted(self.forbidden)}')
        OUTPUT.mkdir(parents=True, exist_ok=True)
        render.save_apng(OUTPUT / f'{self.name}.png', self.frames)
        for name, image in self.stills:
            image.save(OUTPUT / f'{name}.png', optimize=True)
        total = sum(duration for _, duration in self.frames) / 1000
        size = (OUTPUT / f'{self.name}.png').stat().st_size
        print(f'{self.name}: {len(self.frames)} frames, {total:.1f}s, {size} bytes')
        for event in self.events:
            print(f'  {event}')
        tmux('kill-server', check=False)


RELEASE_SCRIPT = """When the message contains "billing release", reply with:

The release notes are ready. Three things need your call before I ship:

1. Which environment should I deploy to, staging or production? I recommend staging.
2. Which checks should run before the deploy: unit, integration, or lint? I recommend unit and lint.
3. What should the release title be? I suggest "Billing 2.4".

When the message contains "changelog", reply with these lines:

Changelog for Billing 2.4:

""" + '\n'.join(f'- Change {index}: updated invoice module {index}.' for index in range(1, 25)) + '\n'


def scene_overview():
    take = Take('demo-overview', 'pending-questions: questions stay in the pane', RELEASE_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.say('1. Claude asks three questions at the end of a response')
    take.enter_prompt('Prepare the billing release.')
    take.wait_for(r'Three things')
    take.hold(900)
    take.say('2. The haiku model extracts them into the pane')
    take.wait_for(r'q3\.')
    take.hold(2200, (r'q1\. Which', r'Recommended: staging'))
    take.still('pane-registered')
    take.say('3. The chat moves on. The questions stay in the pane')
    take.enter_prompt('Write the changelog.')
    take.wait_for(r'Change 24')
    take.hold(2600, (r'pending-questions: 3 pending', None))
    take.say('4. ctrl+x then Tab moves focus to the pane')
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.focus(r'q1\. Which')
    take.hold(1000)
    take.say('5. Enter opens a dialog with the recommendation first')
    take.press('Enter', 'Enter', pause=1.5, duration=1800)
    take.still('single-choice-dialog')
    take.say('6. The answer goes to the session as your prompt')
    take.press('Enter', 'Enter', pause=0.6)
    take.key_label = ''
    take.wait_for(r'\[manual\] q1')
    take.wait_for(r'Noted')
    take.hold(3000, (r'\[manual\] q1', None))
    take.finish()


KINDS_SCRIPT = """When the message contains "rollout", reply with:

Three decisions are left for the rollout:

1. Which region should go first: us-east-1, us-west-2, eu-west-1, eu-central-1, ap-northeast-2, or ap-southeast-1? I recommend eu-west-1.
2. Which alerts should stay on during the rollout: latency, errors, saturation, traffic, disk, or memory? Pick any that apply. I recommend latency and errors.
3. What should the on-call note say? I suggest "Billing 2.4 rollout in progress".
"""


def scene_kinds():
    take = Take('demo-question-kinds', 'pending-questions: three question kinds', KINDS_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.say('Three question kinds, each answered in a dialog')
    take.enter_prompt('Plan the rollout.')
    take.wait_for(r'q3\.')
    take.hold(1800)
    take.say('Multiple choice: the recommended options come first')
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.focus(r'q\d\. Which alerts')
    take.press('Enter', 'Enter', pause=1.5, duration=1400)
    take.say('Enter checks an option. Six options are split into two tabs')
    take.press('Enter', 'Enter', pause=0.4, duration=500)
    take.press('Down', '↓', pause=0.3, duration=300)
    take.press('Enter', 'Enter', pause=0.4, duration=900)
    take.still('multiple-choice-dialog', (r'Alerts 1', r'Chat about this'))
    take.press('Right', '→', pause=0.6, duration=1200)
    take.press('Right', '→', pause=0.6, duration=1600)
    take.press('Enter', 'Enter', pause=0.6, duration=700)
    take.key_label = ''
    take.wait_for(r'\[manual\] q\d\. Which alerts')
    take.wait_for(r'Noted')
    take.hold(1600, (r'\[manual\] q\d\. Which alerts', None))
    take.say('Free-form: the recommended draft, or Type something')
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.focus(r'q\d\. What should')
    take.press('Enter', 'Enter', pause=1.5, duration=1400)
    take.press('Down', '↓', pause=0.3, duration=300)
    take.press('Down', '↓', pause=0.3, duration=400)
    take.key_label = ''
    take.type_text('Billing 2.4 rollout in progress until 18:00')
    take.hold(1200)
    take.still('free-form-dialog')
    take.press('Enter', 'Enter', pause=0.6, duration=700)
    take.key_label = ''
    take.wait_for(r'\[manual\] q\d\. What should')
    take.wait_for(r'Noted')
    take.hold(1200)
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.say('Single choice: five or more options are split into pages')
    take.focus(r'q\d\. Which region')
    take.press('Enter', 'Enter', pause=1.5, duration=1800)
    take.say('More options opens the next page of the same question')
    for _ in range(6):
        if re.search(r'❯\s*\d+\.\s*More options', take.text()):
            break
        take.press('Down', '↓', pause=0.3, duration=300)
    take.press('Enter', 'Enter', pause=1.2, duration=2400)
    take.still('single-choice-pages')
    take.press('Enter', 'Enter', pause=0.6, duration=500)
    take.key_label = ''
    take.wait_for(r'\[manual\] q\d\. Which region')
    take.wait_for(r'Noted')
    take.hold(2000, (r'\[manual\] q\d\. Which region', None))
    take.finish()


AUTO_SCRIPT = """When the message contains "strategy", reply with:

Should I use blue-green or rolling for this deploy? I recommend blue-green.

When the message contains "rollback", reply with:

Should the rollback window be 1 hour or 24 hours?

When the message contains "region tool", call the AskUserQuestion tool once with the question "Which region should go first?", header "Region", and the options "eu-west-1 (Recommended)" and "us-east-1". After the tool returns, reply with: Noted.
"""


def scene_auto():
    take = Take('demo-auto-mode', 'pending-questions: auto mode', AUTO_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.say('Switch to auto mode from the pane')
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.focus(r'Switch to auto')
    take.press('Enter', 'Enter', pause=0.6, duration=900)
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.key_label = ''
    take.hold(900, (r'Mode:', None))
    take.say('The response states a recommendation for the question')
    take.enter_prompt('Choose the deploy strategy.')
    take.wait_for(r'I recommend')
    take.hold(1500)
    take.say('Auto mode sends it as a plugin message, not as your words')
    take.wait_for(r'\[auto\] q1')
    take.wait_for(r'Noted')
    take.hold(3000, (r'\[auto\] q1', None))
    take.still('auto-answered')
    take.say('No stated recommendation: the question stays open for you')
    take.enter_prompt('Set the rollback window.')
    take.wait_for(r'Auto mode leaves')
    take.hold(3200, (r'q2\. Should', r'recommendation\.'))
    take.still('auto-left-open')
    take.say('AskUserQuestion with a (Recommended) option is answered too')
    take.enter_prompt('Use the region tool.')
    take.wait_for(r'\[auto\] q3|eu-west-1')
    take.wait_for(r'Use the region tool[\s\S]*Noted\.')
    take.hold(2800)
    take.finish()


CHAIN_SCRIPT = """The rules below override the Noted rule, except for check-f.

When the message contains "checklist", reply with:

Should I run check-a, yes or no? I recommend yes.

When a message contains "check-a", do not reply with Noted. Reply with:

Should I run check-b, yes or no? I recommend yes.

When a message contains "check-b", do not reply with Noted. Reply with:

Should I run check-c, yes or no? I recommend yes.

When a message contains "check-c", do not reply with Noted. Reply with:

Should I run check-d, yes or no? I recommend yes.

When a message contains "check-d", do not reply with Noted. Reply with:

Should I run check-e, yes or no? I recommend yes.

When a message contains "check-e", do not reply with Noted. Reply with:

Should I run check-f, yes or no? I recommend yes.

When a message contains "check-f", reply with one line: Noted.
"""


def scene_pause():
    take = Take('demo-auto-pause', 'pending-questions: auto mode pause', CHAIN_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.focus(r'Switch to auto')
    take.press('Enter', 'Enter', pause=0.6, duration=500)
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.key_label = ''
    take.say('Each automatic answer starts the next turn')
    take.enter_prompt('Run the checklist.')
    take.wait_for(r'\[auto\] q2', timeout=180)
    take.hold(700)
    take.wait_for(r'\[auto\] q4', timeout=240)
    take.hold(700)
    take.say('After 5 answers in a row, auto mode pauses')
    take.wait_for(r'Auto mode paused|\[auto\] q5', timeout=240)
    take.hold(600)
    take.wait_for(r'q6\.', timeout=240)
    take.say('The 6th question waits until you answer')
    take.hold(3500, (r'q6\. Should', r'Recommended'))
    take.still('auto-paused')
    take.finish()


CORRECTION_SCRIPT = """When the message contains "cutover", reply with:

Two things are open for the cutover:

1. Which database should go first, orders or invoices? I recommend orders.
2. Should I notify the support team, yes or no? I recommend yes.

When the message contains "Start with orders", reply with: Starting with the orders database.
"""


def scene_corrections():
    take = Take('demo-corrections', 'pending-questions: closing and correcting', CORRECTION_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.say('Two questions are open')
    take.enter_prompt('Plan the cutover.')
    take.wait_for(r'q2\.')
    take.hold(1500)
    take.say('You answer in the chat instead of the pane')
    take.enter_prompt('Start with orders.')
    take.wait_for(r'Starting with the orders')
    take.hold(900)
    take.say('The question closes as [resolved], with the evidence quoted')
    take.wait_for(r'\[resolved\] q1', timeout=120)
    take.hold(3000, (r'\[resolved\] q1', r'\[ Reopen'))
    take.still('resolved-history', (r'\[resolved\] q1', r'\[ Reopen'))
    take.say('Not a question closes a wrong entry')
    take.chord('ctrl+x Tab', 'C-x', 'Tab')
    take.focus(r'Not a question')
    take.hold(900)
    take.press('Enter', 'Enter', pause=0.8, duration=1500)
    take.wait_for(r'\[dismissed\] q2')
    take.hold(1500, (r'\[dismissed\] q2', None))
    take.say('Reopen restores a wrongly closed entry')
    take.focus(r'Reopen')
    take.hold(700)
    take.press('Enter', 'Enter', pause=0.8, duration=1800)
    take.hold(1400)
    take.say('Rescan reads the last response again with the sonnet model')
    take.focus(r'Rescan')
    take.press('Enter', 'Enter', pause=0.5, duration=1400)
    take.wait_for(r'Rescan found no new|new question', timeout=120)
    take.hold(2200, (r'Rescan found no new questions\.|new question', None))
    take.finish()


RECOVERY_SCRIPT = """When the message contains "migration", reply with:

Should the migration run tonight or on Sunday? I recommend tonight.
"""


def scene_recovery():
    take = Take('demo-crash-recovery', 'pending-questions: crash recovery', RECOVERY_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.say('A response asks a question and the pane registers it')
    take.enter_prompt('Schedule the migration.')
    take.wait_for(r'q1\.')
    take.hold(1800, (r'q1\. Should', None))
    pid = take.claude_pid()
    session = take.session_id()
    take.say('The process dies: kill -9 (no chance to save anything)')
    os.kill(pid, signal.SIGKILL)
    take.key_label = 'kill -9'
    take.wait_for(r'killed|(?m)^\$\s*$')
    take.hold(2000, (r'killed', None))
    tmux('send-keys', '-t', 'demo', 'C-l')
    time.sleep(0.5)
    take.key_label = ''
    take.say('Resume the session')
    take.type_text(f'claude --resume {session}')
    take.press('Enter', 'Enter', pause=0.4)
    take.key_label = ''
    take.wait_for(r'❯\s', timeout=60)
    time.sleep(4)
    take.open_pane()
    take.say('The question is back, restored from its file')
    take.wait_for(r'q1\.')
    take.hold(3200, (r'q1\. Should', r'Recommended'))
    take.still('recovered-question', (r'q1\. Should', r'Recommended'))
    take.finish()


OTHER_SCRIPT = """When the message contains "invoice", reply with:

Should invoices be sent daily or weekly? I recommend weekly.
"""


def scene_other_sessions():
    take = Take('demo-other-sessions', 'pending-questions: other sessions', OTHER_SCRIPT)
    take.start_claude()
    take.open_pane()
    take.say('Session A leaves a question open')
    take.enter_prompt('Plan the invoice job.')
    take.wait_for(r'q1\.')
    take.hold(1800, (r'q1\. Should', None))
    take.say('Session A exits')
    take.type_text('/exit')
    time.sleep(0.3)
    take.press('Enter', 'Enter', pause=0.5)
    take.wait_for(r'(?m)^\$\s*$', timeout=30)
    tmux('send-keys', '-t', 'demo', 'C-l')
    time.sleep(0.4)
    take.hold(900)
    take.say('Session B starts in the same working directory')
    take.type_text('claude')
    take.press('Enter', 'Enter', pause=0.4)
    take.key_label = ''
    take.wait_for(r'❯\s', timeout=60)
    time.sleep(4)
    take.open_pane()
    take.say('The pane lists the question with its resume command')
    take.wait_for(r'pending in another')
    take.hold(3600, (r'1 pending in', r'[0-9a-f-]{8,}'))
    take.still('other-session-line', (r'1 pending in', r'[0-9a-f-]{8,}'))
    take.finish()


SCENES = {
    'overview': scene_overview,
    'kinds': scene_kinds,
    'auto': scene_auto,
    'pause': scene_pause,
    'corrections': scene_corrections,
    'recovery': scene_recovery,
    'other': scene_other_sessions,
}


# 추출 모델의 출력이 take 마다 달라 장면이 멈출 때가 있다.
MAX_ATTEMPTS = 4


def make_social_preview():
    image = render.social_preview(
        OUTPUT / 'pane-registered.png',
        'pending-questions',
        'A Claude Code plugin that keeps unanswered questions in a pane',
    )
    image.save(OUTPUT / 'social-preview.png', optimize=True)


def main():
    prepare_home()
    names = sys.argv[1:] or list(SCENES)
    for name in names:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                SCENES[name]()
                break
            except TimeoutError as error:
                print(f'FAILED {name} (attempt {attempt}): {error}')
    if (OUTPUT / 'pane-registered.png').exists():
        make_social_preview()


if __name__ == '__main__':
    main()

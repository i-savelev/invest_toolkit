#!/usr/bin/env python3
"""
Собирает незакоммиченные изменения из Git и формирует промпт для LLM.

Особенности:
- Показывает только существенные изменения (игнорирует .log, .pyc, __pycache__ и т.д.)
- Форматирует как маркдаун с подсветкой синтаксиса
- Добавляет структуру затронутых файлов
- Сохраняет в файл и копирует в буфер обмена
"""
import subprocess
import sys
import os
import re
from pathlib import Path
from typing import List, Dict

class GitChangesPrompt:
    IGNORE_PATTERNS = [
        r'\.log$',
        r'\.pyc$',
        r'\.pyo$',
        r'\.pyd$',
        r'\.db$',
        r'\.sqlite$',
        r'\.sqlite3$',
        r'__pycache__',
        r'\.egg-info',
        r'\.venv',
        r'venv',
        r'\.vscode',
        r'\.idea',
        r'\.git',
        r'\.DS_Store',
        r'node_modules',
        r'\.ipynb_checkpoints',
        r'\.output',
    ]

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.changes: Dict[str, str] = {}

    def _should_ignore(self, filepath: str) -> bool:
        """Игнорировать бинарные/временные файлы."""
        for pattern in self.IGNORE_PATTERNS:
            if re.search(pattern, filepath, re.IGNORECASE):
                return True
        return False

    def _run_git(self, args: List[str]) -> str:
        """Выполнить git-команду."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"Git error: {result.stderr.strip()}")
            return result.stdout
        except FileNotFoundError:
            raise RuntimeError("Git не установлен или не найден в PATH")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Git-команда превысила время ожидания")

    def collect_changes(self) -> None:
        """Собрать все незакоммиченные изменения."""
        # 1. Изменённые и новые файлы (отслеживаемые)
        try:
            diff = self._run_git(["diff", "--no-color", "HEAD"])
        except RuntimeError:
            # Если нет коммитов — сравниваем с пустым деревом
            diff = self._run_git(["diff", "--no-color", "--cached"])

        # 2. Новые неотслеживаемые файлы
        untracked = self._run_git(["ls-files", "--others", "--exclude-standard"])
        for filepath in untracked.strip().splitlines():
            if filepath and not self._should_ignore(filepath):
                try:
                    content = Path(self.repo_path / filepath).read_text(encoding="utf-8")
                    self.changes[f"UNTRACKED:{filepath}"] = content
                except (UnicodeDecodeError, FileNotFoundError):
                    self.changes[f"UNTRACKED_BINARY:{filepath}"] = "[Бинарный файл или ошибка чтения]"

        # 3. Парсим diff
        current_file = None
        current_diff = []
        for line in diff.splitlines():
            if line.startswith("diff --git"):
                if current_file and not self._should_ignore(current_file):
                    self.changes[current_file] = "\n".join(current_diff)
                # Извлекаем имя файла: a/path b/path → path
                match = re.search(r'diff --git a/(.+) b/(.+)', line)
                current_file = match.group(2) if match else "unknown"
                current_diff = [line]
            elif current_file:
                current_diff.append(line)
        
        if current_file and not self._should_ignore(current_file):
            self.changes[current_file] = "\n".join(current_diff)

    def format_prompt(self) -> str:
        """Форматировать изменения как промпт для LLM."""
        if not self.changes:
            return "Нет незакоммиченных изменений в репозитории."

        # Структура затронутых файлов
        file_tree = {}
        for filepath in self.changes.keys():
            clean_path = filepath.replace("UNTRACKED:", "").replace("UNTRACKED_BINARY:", "")
            parts = Path(clean_path).parts
            node = file_tree
            for part in parts:
                node = node.setdefault(part, {})

        def render_tree(tree: Dict, indent: str = "") -> List[str]:
            lines = []
            for i, (name, subtree) in enumerate(sorted(tree.items())):
                is_last = i == len(tree) - 1
                prefix = "└── " if is_last else "├── "
                lines.append(f"{indent}{prefix}{name}")
                if subtree:
                    next_indent = indent + ("    " if is_last else "│   ")
                    lines.extend(render_tree(subtree, next_indent))
            return lines

        prompt = [
            "# 📦 Незакоммиченные изменения в репозитории",
            "",
            "## 🌳 Структура изменённых файлов",
            "```",
            *render_tree(file_tree),
            "```",
            "",
            "## 📄 Детали изменений",
            ""
        ]

        for filepath, content in sorted(self.changes.items()):
            is_untracked = filepath.startswith("UNTRACKED:")
            is_binary = filepath.startswith("UNTRACKED_BINARY:")
            clean_path = filepath.replace("UNTRACKED:", "").replace("UNTRACKED_BINARY:", "")

            prompt.append(f"### {'🆕 Новый файл' if is_untracked else '✏️ Изменения'}: `{clean_path}`")
            prompt.append("")

            if is_binary:
                prompt.append("```\n[Бинарный файл или ошибка чтения]\n```")
            elif is_untracked:
                # Для новых файлов показываем полное содержимое с подсветкой
                ext = Path(clean_path).suffix.lstrip(".").lower() or "text"
                prompt.append(f"```{ext}")
                prompt.append(content.rstrip())
                prompt.append("```")
            else:
                # Для diff показываем как есть
                prompt.append("```diff")
                prompt.append(content.rstrip())
                prompt.append("```")
            
            prompt.append("")

        prompt.append("## ❓ Задача")
        prompt.append("")
        prompt.append("Проанализируй изменения выше и:")
        prompt.append("- сформируй тект для пулл реквеста. Структурируй изменения по пунктам")
        prompt.append("- делай описание кратким, без эмодзи")
        prompt.append("- пункты отделяй простыми прочерками")
        
        return "\n".join(prompt)

    def save_to_file(self, filepath: str = ".output/git_changes_prompt.md") -> Path:
        """Сохранить промпт в файл."""
        content = self.format_prompt()
        path = Path(filepath)
        if path.exists():
            path.unlink()
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path


def main():
    collector = GitChangesPrompt()
    try:
        collector.collect_changes()
        path = collector.save_to_file()
        
        print(f"✅ Промпт сохранён в: {path.absolute()}")
        
        # Показать статистику
        total_files = len(collector.changes)
        untracked = sum(1 for f in collector.changes if f.startswith("UNTRACKED:"))
        print(f"\n📊 Изменения: {total_files} файлов ({untracked} новых, {total_files - untracked} изменённых)")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
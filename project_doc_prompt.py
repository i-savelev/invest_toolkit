import os
from pathlib import Path
from typing import List, Dict, Optional


def _get_directory_structure(start_path: Path, exclude_folders: Optional[List[str]] = None) -> str:
    """
    Формирует строковое представление дерева файлов и папок.

    Визуализирует структуру директории в виде иерархического списка с использованием
    символов └── и ├──. Папки из списка исключений не включаются в структуру.

    :param start_path: Путь к корневой папке проекта.
    :param exclude_folders: Список имен папок для исключения из структуры (например, ['.git', 'venv']).
    :returns: Строка с визуальным представлением структуры проекта.
    :Example:

        >>> from pathlib import Path
        >>> tree = get_directory_structure(Path('.'), exclude_folders=['.git', 'venv'])
        >>> print(tree)
        .
        └── src/
            └── main.py
    """
    if exclude_folders is None:
        exclude_folders = []
        
    lines = []
    start_path = start_path.resolve()
    
    lines.append(f"{start_path.name}")

    def add_to_lines(current_path: Path, prefix: str = ""):
        try:
            items = sorted(current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return

        for i, item in enumerate(items):
            # Исключаем папки из списка exclude_folders
            if item.is_dir() and item.name in exclude_folders:
                continue
                
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            
            lines.append(f"{prefix}{connector}{item.name}")

            if item.is_dir():
                extension = "    " if is_last else "│   "
                add_to_lines(item, prefix + extension)

    add_to_lines(start_path)
    return "\n".join(lines)


def _is_file_included(
    file_path: Path,
    include_extensions: List[str],
    exclude_filenames: List[str],
    exclude_folders: List[str]
) -> bool:
    """
    Проверяет, должен ли файл быть включен в анализ содержимого.

    Фильтрует файлы на основе расширений, имен файлов и имен папок.
    Если файл не проходит хотя бы один фильтр исключения или не входит
    в список разрешенных расширений, функция вернет False.

    :param file_path: Полный путь к файлу.
    :param include_extensions: Список разрешенных расширений (например, ['.py', '.txt']).
    :param exclude_filenames: Список имен файлов для исключения (например, ['__init__.py']).
    :param exclude_folders: Список имен папок для исключения (например, ['.git', 'venv']).
    :returns: True, если файл должен быть обработан, иначе False.
    :Example:

        >>> path = Path('src/main.py')
        >>> is_file_included(path, ['.py'], ['test.py'], ['build'])
        True
    """
    if include_extensions and file_path.suffix not in include_extensions:
        return False

    if file_path.name in exclude_filenames:
        return False

    for part in file_path.parts:
        if part in exclude_folders:
            return False

    return True


def _get_language_hint(file_path: Path, lang_mapping: Dict[str, str]) -> str:
    """
    Определяет подсказку языка для блока кода в Markdown.

    Ищет расширение файла в словаре мэппинга. Если расширение не найдено,
    возвращает пустую строку.

    :param file_path: Путь к файлу.
    :param lang_mapping: Словарь вида {'.py': 'python', '.js': 'javascript'}.
    :returns: Строка с идентификатором языка для Markdown.
    :Example:

        >>> mapping = {'.py': 'python'}
        >>> get_language_hint(Path('script.py'), mapping)
        'python'
    """
    return lang_mapping.get(file_path.suffix, "")


def _read_file_content(file_path: Path) -> str:
    """
    Читает содержимое файла с обработкой ошибок кодировки.

    Пытается прочитать файл в UTF-8. В случае ошибки игнорирует проблемные символы,
    чтобы скрипт не прерывался на бинарных или поврежденных файлах.

    :param file_path: Путь к читаемому файлу.
    :returns: Содержимое файла в виде строки.
    :Example:

        >>> content = read_file_content(Path('README.md'))
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return "# Ошибка чтения файла"


def _collect_files_content(
    start_path: Path,
    include_extensions: List[str],
    exclude_filenames: List[str],
    exclude_folders: List[str],
    lang_mapping: Dict[str, str]
) -> str:
    """
    Собирает содержимое всех подходящих файлов в форматированный Markdown.

    Проходит по всем файлам в директории, применяет фильтры и формирует
    секции с заголовками и блоками кода.

    :param start_path: Корневая папка для сканирования.
    :param include_extensions: Список расширений для включения.
    :param exclude_filenames: Список имен файлов для исключения.
    :param exclude_folders: Список папок для исключения.
    :param lang_mapping: Словарь для подсветки синтаксиса.
    :returns: Строка с содержимым всех файлов в формате Markdown.
    :Example:

        >>> content = collect_files_content(Path('.'), ['.py'], [], [], {'.py': 'python'})
    """
    sections = []
    all_files = sorted(start_path.rglob('*'))
    
    for file_path in all_files:
        if not file_path.is_file():
            continue
            
        if not _is_file_included(file_path, include_extensions, exclude_filenames, exclude_folders):
            continue

        try:
            relative_path = file_path.relative_to(start_path)
        except ValueError:
            relative_path = file_path.name
            
        header = f"## {relative_path}"
        lang = _get_language_hint(file_path, lang_mapping)
        content = _read_file_content(file_path)
        code_block = f"```{lang}\n{content}\n```"
        
        sections.append(f"{header}\n{code_block}")

    return "\n\n".join(sections)


def generate_project_documentation(
    source_dir: str,
    output_file: str,
    include_extensions: Optional[List[str]] = None,
    exclude_filenames: Optional[List[str]] = None,
    exclude_folders: Optional[List[str]] = None,
    lang_mapping: Optional[Dict[str, str]] = None
) -> None:
    """
    Главная функция для генерации итогового Markdown файла.

    Объединяет структуру проекта и содержимое файлов в один документ.
    Создаёт файл по указанному пути.

    :param source_dir: Путь к исходной папке с проектом.
    :param output_file: Путь для сохранения итогового .md файла.
    :param include_extensions: Список расширений для анализа (по умолчанию все).
    :param exclude_filenames: Список файлов для исключения из анализа.
    :param exclude_folders: Список папок для исключения из анализа и структуры.
    :param lang_mapping: Словарь расширения -> язык подсветки.
    :returns: None (результат записывается в файл).
    :Example:

        >>> generate_project_documentation(
        ...     source_dir='./my_project',
        ...     output_file='./result.md',
        ...     include_extensions=['.py'],
        ...     exclude_folders=['venv', '.git']
        ... )
    """
    if include_extensions is None:
        include_extensions = []
    if exclude_filenames is None:
        exclude_filenames = []
    if exclude_folders is None:
        exclude_folders = []
    if lang_mapping is None:
        lang_mapping = {}

    source_path = Path(source_dir).resolve()
    output_path = Path(output_file).resolve()

    # 1. Формируем структуру (с исключениями папок)
    structure_text = _get_directory_structure(source_path, exclude_folders)

    # 2. Формируем содержимое (с фильтрами)
    content_text = _collect_files_content(
        source_path,
        include_extensions,
        exclude_filenames,
        exclude_folders,
        lang_mapping
    )

    # 3. Собираем итоговый документ
    final_document = f"# Документация проекта\n\n"
    final_document += f"## Структура проекта\n\n"
    final_document += f"```text\n{structure_text}\n```\n\n"
    final_document += content_text

    # 4. Записываем в файл
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_document)

    print(f"Документация успешно сохранена в: {output_path}")


if __name__ == "__main__":
    # Пример использования скрипта
    # Замените пути на актуальные для вашего проекта
    
    generate_project_documentation(
        source_dir=".",  # Текущая папка
        output_file=".output/project_dump.md",  # Имя выходного файла
        include_extensions=[".py", '.toml'],  # Какие файлы читать
        exclude_filenames=['.DS_Store', 'README.md'],  # Какие файлы игнорировать
        exclude_folders=[
            ".git", 
            "__pycache__", 
            ".venv", 
            ".idea", 
            "personal_notebooks", 
            'scrapper_reports', 
            '.log',
            'invest_toolkit.egg-info',
            '.output',
            '.reports',
            '.DS_Store',
            'scrapper_reports_archive',
            ],
        lang_mapping={  # Подсветка синтаксиса
            ".py": "python",
            ".md": "markdown",
            ".txt": "text",
            ".js": "javascript"
        }
    )
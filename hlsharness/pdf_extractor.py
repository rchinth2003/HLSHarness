"""PdfExtractor — extract plain text from .pdf files or pass .txt files through."""

from __future__ import annotations

from pathlib import Path


class PdfExtractor:
    """Extract text from a spec file for use by SpecInterpreter.

    - ``.pdf`` files are parsed with *pypdf*; all pages are concatenated.
    - All other extensions are read as UTF-8 text via ``Path.read_text()``.
    """

    def extract(self, path: Path) -> str:
        """Return the full text content of *path*.

        Parameters
        ----------
        path:
            Absolute or relative path to a ``.pdf``, ``.txt``, ``.yaml``,
            ``.json``, or any other text-based spec file.

        Raises
        ------
        OSError
            If the file does not exist or cannot be read.
        """
        if path.suffix.lower() == ".pdf":
            return self._extract_pdf(path)
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = (page.extract_text() or "" for page in reader.pages)
        return "\n".join(pages)

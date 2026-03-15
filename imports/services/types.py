"""Dataclasses used to serialize preview payloads into the session."""

from dataclasses import asdict, dataclass


@dataclass
class ImportPreview:
    batch_name: str
    import_type: str
    required_columns: list[str]
    file_name: str
    total_rows: int
    valid_rows: list[dict]
    errors: list[dict]
    duplicates: list[dict]

    def to_dict(self):
        """Convert the preview dataclass to a session-safe dictionary."""
        return asdict(self)


@dataclass
class WorkbookImportPreview:
    batch_name: str
    import_type: str
    required_columns: list[str]
    file_name: str
    total_rows: int
    valid_rows: list[dict]
    errors: list[dict]
    duplicates: list[dict]
    sections: list[dict]
    skipped_rows: list[dict]

    def to_dict(self):
        """Convert the workbook preview dataclass to a session-safe dictionary."""
        return asdict(self)

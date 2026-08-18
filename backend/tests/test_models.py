from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, ColumnProfile, Dataset, DatasetStatus


def test_dataset_profiles_are_persisted_and_deleted_together() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        dataset = Dataset(
            original_filename="contoh.csv",
            source_type="file_upload",
            file_type="csv",
            original_file_key="originals/id.csv",
            snapshot_key="snapshots/id.ndjson.gz",
            status=DatasetStatus.COMPLETED,
            row_count=2,
            column_count=1,
            preview=[{"_source_row": 2, "nama": "ANI"}],
        )
        dataset.column_profiles.append(
            ColumnProfile(
                original_name="nama",
                display_name="nama",
                position=0,
                inferred_type="text",
                candidate_role="text",
                null_count=0,
                empty_count=0,
                unique_count=2,
                sample_values=["ANI", "BUDI"],
            )
        )
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    with Session(engine) as session:
        saved = session.get(Dataset, dataset_id)
        assert saved is not None
        assert saved.column_profiles[0].sample_values == ["ANI", "BUDI"]
        session.delete(saved)
        session.commit()
        assert session.scalars(select(ColumnProfile)).all() == []

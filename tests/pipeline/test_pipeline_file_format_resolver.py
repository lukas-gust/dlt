
import dlt
import pytest
from dlt.common.exceptions import DestinationIncompatibleLoaderFileFormatException

def test_file_format_resolution()  -> None:
    p = dlt.pipeline(pipeline_name="managed_state_pipeline")

    class cp():
        def __init__(self) -> None:
            self.preferred_loader_file_format = None
            self.supported_loader_file_formats = []
            self.preferred_staging_file_format = None
            self.supported_staging_file_formats = []

    destcp = cp()
    stagecp = cp()

    # check regular resolution
    destcp.preferred_loader_file_format = "jsonl"
    destcp.supported_loader_file_formats = ["jsonl", "insert_values", "parquet"]
    assert p._resolve_loader_file_format("some", "some", destcp, None, None) == "jsonl"

    # check resolution with input
    assert p._resolve_loader_file_format("some", "some", destcp, None, "parquet") == "parquet"

    # check invalid input
    with pytest.raises(DestinationIncompatibleLoaderFileFormatException):
        assert p._resolve_loader_file_format("some", "some", destcp, None, "csv")

    # check staging resolution with clear preference
    destcp.supported_staging_file_formats = ["jsonl", "insert_values", "parquet"]
    destcp.preferred_staging_file_format = "insert_values"
    stagecp.supported_loader_file_formats = ["jsonl", "insert_values", "parquet"]
    assert p._resolve_loader_file_format("some", "some", destcp, stagecp, None) == "insert_values"

    # check invalid input
    with pytest.raises(DestinationIncompatibleLoaderFileFormatException):
        p._resolve_loader_file_format("some", "some", destcp, stagecp, "csv")

    # check staging resolution where preference does not match
    destcp.supported_staging_file_formats = ["insert_values", "parquet"]
    destcp.preferred_staging_file_format = "csv"
    stagecp.supported_loader_file_formats = ["jsonl", "insert_values", "parquet"]
    assert p._resolve_loader_file_format("some", "some", destcp, stagecp, None) == "insert_values"
    assert p._resolve_loader_file_format("some", "some", destcp, stagecp, "parquet") == "parquet"

    # check incompatible staging
    destcp.supported_staging_file_formats = ["insert_values", "csv"]
    destcp.preferred_staging_file_format = "csv"
    stagecp.supported_loader_file_formats = ["jsonl", "parquet"]
    with pytest.raises(DestinationIncompatibleLoaderFileFormatException):
        p._resolve_loader_file_format("some", "some", destcp, stagecp, None)
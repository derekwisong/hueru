import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# This assumes pytest is run from the project root directory (`/home/derek/src/hueru`)
from hueru.screen import ScreenScanner


@pytest.fixture
def mock_dependencies():
    """
    A pytest fixture to mock external dependencies (GStreamer, GLib, threading)
    for all tests in this file. This prevents the code from trying to actually
    capture the screen.
    """
    with patch('hueru.screen.threading.Thread') as mock_thread, \
         patch('hueru.screen.GLib') as mock_glib, \
         patch('hueru.screen.Gst') as mock_gst:

        # Configure GStreamer mock for successful pipeline creation
        mock_pipeline = MagicMock()
        mock_pipeline.set_state.return_value = mock_gst.StateChangeReturn.SUCCESS
        mock_gst.parse_launch.return_value = mock_pipeline

        yield {
            "thread": mock_thread,
            "glib": mock_glib,
            "gst": mock_gst,
            "pipeline": mock_pipeline,
        }


def test_create_screen_scanner(mock_dependencies):
    """
    Tests the initialization and cleanup of the ScreenScanner class.
    It verifies that all the necessary setup (GStreamer, threading) and
    teardown logic is called correctly.
    """
    # Extract mocks from the fixture for making assertions
    MockGst = mock_dependencies["gst"]
    MockGLib = mock_dependencies["glib"]
    MockThread = mock_dependencies["thread"]
    mock_pipeline = mock_dependencies["pipeline"]

    with ScreenScanner(width=200, height=150) as scanner:
        assert scanner is not None
        assert scanner.width == 200
        assert scanner.height == 150

        MockGst.init.assert_called_with(None)
        mock_pipeline.get_by_name.assert_called_with("sink")
        MockGLib.MainLoop.assert_called_once()
        MockThread.assert_called_once_with(target=MockGLib.MainLoop.return_value.run)
        MockThread.return_value.start.assert_called_once()
        mock_pipeline.set_state.assert_any_call(MockGst.State.PLAYING)

    # Verify cleanup on __exit__
    mock_pipeline.set_state.assert_called_with(MockGst.State.NULL)
    MockGLib.MainLoop.return_value.quit.assert_called_once()


def test_get_region_color(mock_dependencies):
    """
    Tests the get_region_color method with a manually set numpy array as a frame,
    bypassing the capture pipeline.
    """
    scanner = ScreenScanner(width=100, height=100)

    # Create a dummy 100x100 frame, half black, half white
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[:, 50:] = 255  # Right half is white
    scanner.latest_frame = frame

    assert scanner.get_region_color(0.0, 0.0, 0.5, 1.0) == (0, 0, 0)
    assert scanner.get_region_color(0.5, 0.0, 1.0, 1.0) == (255, 255, 255)
    assert scanner.get_region_color(0.25, 0.0, 0.75, 1.0) == (127, 127, 127)
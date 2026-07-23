from unittest.mock import patch

import pytest

from utils.retry import retry_on_exception


class CustomError(Exception):
    pass


@pytest.mark.unit
def test_returns_immediately_on_success():
    call_count = 0

    @retry_on_exception(max_retries=3, base_delay=0.0, exceptions=(CustomError,))
    def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    assert succeed() == "ok"
    assert call_count == 1


@pytest.mark.unit
def test_retries_on_specified_exception():
    call_count = 0

    @retry_on_exception(max_retries=3, base_delay=0.0, exceptions=(CustomError,))
    def fail_twice():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CustomError("fail")
        return "ok"

    assert fail_twice() == "ok"
    assert call_count == 3


@pytest.mark.unit
def test_raises_after_max_retries_exhausted():
    call_count = 0

    @retry_on_exception(max_retries=2, base_delay=0.0, exceptions=(CustomError,))
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise CustomError("always fail")

    with pytest.raises(CustomError, match="always fail"):
        always_fail()
    assert call_count == 2


@pytest.mark.unit
def test_does_not_catch_unspecified_exception():
    call_count = 0

    @retry_on_exception(max_retries=3, base_delay=0.0, exceptions=(CustomError,))
    def wrong_error():
        nonlocal call_count
        call_count += 1
        raise ValueError("wrong type")

    with pytest.raises(ValueError, match="wrong type"):
        wrong_error()
    assert call_count == 1


@pytest.mark.unit
@patch("utils.retry.time.sleep")
def test_exponential_backoff_delays(mock_sleep):
    call_count = 0

    @retry_on_exception(max_retries=4, base_delay=1.0, exceptions=(CustomError,))
    def fail_thrice():
        nonlocal call_count
        call_count += 1
        if call_count < 4:
            raise CustomError("fail")
        return "ok"

    result = fail_thrice()
    assert result == "ok"
    assert call_count == 4
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)
    mock_sleep.assert_any_call(4.0)
    assert mock_sleep.call_count == 3


@pytest.mark.unit
def test_preserves_function_metadata():
    @retry_on_exception(max_retries=1, base_delay=0.0, exceptions=(CustomError,))
    def documented_function():
        """This is a docstring."""
        return True

    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "This is a docstring."

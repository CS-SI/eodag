from requests.models import Response

from eodag.utils.exceptions import RequestError


def test_request_error_includes_response_text():
    """
    This test triggers a bug in RequestError due to the code doing an if on a response
    object without realizing that a response object evaluates to False if it doesn't
    have a status code 200. This resulted in error text from the provider not being
    included in the error.
    """
    original_exception = Exception()
    response = Response()
    response.status_code = 400
    response._content = b"*** my response text ***"
    original_exception.response = response

    error = RequestError.from_error(original_exception)

    # Verify that the error message from the server is included in the error
    assert "*** my response text ***" in str(error)
    assert error.status_code == 400

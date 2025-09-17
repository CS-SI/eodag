from unittest import TestCase

from httpx import Response

from eodag.utils.exceptions import RequestError


class TestRequestError(TestCase):
    def test_request_error_includes_response_text(self):
        """
        This test triggers a bug in RequestError due to the code doing an if on a response
        object without realizing that a response object evaluates to False if it doesn't
        have a status code 200. This resulted in error text from the provider not being
        included in the error.
        """
        original_exception = Exception()
        response = Response(status_code=400, content=b"*** my response text ***")
        original_exception.response = response

        error = RequestError.from_error(original_exception)

        # Verify that the error message from the server is included in the error
        self.assertIn("*** my response text ***", str(error))
        self.assertEqual(error.status_code, 400)

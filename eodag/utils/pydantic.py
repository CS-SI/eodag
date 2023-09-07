from pydantic import BaseModel as PydanticBaseModel
from pydantic import ValidationError as PydanticValidationError


class ValidationError(Exception):
    """Error validating data"""

    def __init__(self, message):
        """
        Initialize the ValidationError instance with a message.

        :param message: The error message to be displayed.
        """
        self.message = message


class BaseModel(PydanticBaseModel):
    """
    A base model class that extends Pydantic's BaseModel class.
    """

    @classmethod
    def model_validate(cls, value):
        """
        Validate the given value using Pydantic's model validation.

        :param value: The value to be validated.
        :return: The validated value.
        :raises ValidationError: If the value is not valid according to the model's schema.
        """
        try:
            return super().model_validate(value)
        except PydanticValidationError as e:
            raise ValidationError(e.errors()) from e

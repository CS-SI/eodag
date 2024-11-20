from collections import UserDict

from pydantic.fields import Field

from eodag.types import annotated_dict_to_model


class QueryablesDict(UserDict):
    """Class inheriting from UserDict which contains queryables with their annotated type;

    :param additional_properties: if additional properties (properties not given in EODAG config)
     are allowed
    :param kwargs: named arguments to initialise the dict (queryable keys + annotated types)
    """

    additional_properties: bool = Field(True)

    def __init__(self, additional_properties: bool, **kwargs):
        self.additional_properties = additional_properties
        super().__init__(kwargs)

    def _repr_html_(self, embedded=False):
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                        {type(self).__name__}&ensp;({len(self)})
                        </td></tr></thead>
                    """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""
        return (
            f"<table>{thead}<tbody>"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                        <details><summary style='color: grey;'>
                            <span style='color: black'>'{k}'</span>:&ensp;
                            {{
                                {"'alias': '<span style='color: black'>" + v.__metadata__[0].alias + "</span>',&ensp;"
                if v.__metadata__[0].alias else ""}
                                {"'type': '<span style='color: black'>" + str(v.__args__[0]) + "</span>',&ensp;"
                if not hasattr(v.__args__[0], "__name__") or v.__args__[0].__name__ == "Union" else(
                                "'type': '<span style='color: black'>" + v.__args__[0].__name__ + "</span>',&ensp;")}
                                {"'default': '<span style='color: black'>" +
                                 str(v.__metadata__[0].get_default()) + "</span>',&ensp;"
                if v.__metadata__[0].get_default() else ""}
                                {"'required': '<span style='color: black'>" +
                                 str(v.__metadata__[0].is_required()) + "</span>',&ensp;"}
                            }}
                        </summary>
                        </details>
                        </td></tr>
                        """
                    for k, v in self.items()
                ]
            )
            + "</tbody></table>"
        )

    def get_model(self):
        """
        converts the object from the QueryablesDict class to an object of the pydantic Model class
        so that validation can be performed
        :return: pydantic BaseModel of the queryables dict
        """
        return annotated_dict_to_model("Queryables", self.data)

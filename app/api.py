import inspect
from functools import wraps
from typing import Iterable, TypeVar, Optional, Type, List

from schematics import Model
from schematics.common import NOT_NONE
from schematics.types import UUIDType, StringType, ModelType, ListType, DateType, BaseType, DictType, IntType, \
    BooleanType
from schematics.exceptions import DataError
from schematics.types.base import TypeMeta
from flask import abort, request, Response, jsonify


# Inheriting this class will make an enum exhaustive
class EnumMeta(TypeMeta):
    def __new__(mcs, name, bases, attrs):
        attrs['choices'] = [v for k, v in attrs.items(
        ) if not k.startswith('_') and k.isupper()]
        return TypeMeta.__new__(mcs, name, bases, attrs)


class ApproxDateType(DateType):
    formats = ['%Y-%m']


# Intentionally non-exhaustive
class DemoResultType(StringType):
    ANY = 'ANY'
    ANY_CHARGE = 'ANY_CHARGE'

    # Errors
    ERROR_INVALID_CREDENTIALS = 'ERROR_INVALID_CREDENTIALS'
    ERROR_ANY_PROVIDER_MESSAGE = 'ERROR_ANY_PROVIDER_MESSAGE'
    ERROR_CONNECTION_TO_PROVIDER = 'ERROR_CONNECTION_TO_PROVIDER'

    # Identity check specific
    NO_MATCHES = 'NO_MATCHES'
    ONE_NAME_ADDRESS_MATCH = 'ONE_NAME_ADDRESS_MATCH'
    ONE_NAME_DOB_MATCH = 'ONE_NAME_DOB_MATCH'
    TWO_NAME_ADDRESS_MATCHES = 'TWO_NAME_ADDRESS_MATCHES'
    ONE_NAME_ADDRESS_ONE_NAME_DOB_MATCH = 'ONE_NAME_ADDRESS_ONE_NAME_DOB_MATCH'
    ONE_NAME_ADDRESS_DOB_MATCH = 'ONE_NAME_ADDRESS_DOB_MATCH'
    MORTALITY_MATCH = 'MORTALITY_MATCH'
    ONE_NAME_ADDRESS_MORTALITY_MATCH = 'ONE_NAME_ADDRESS_MORTALITY_MATCH'
    ONE_NAME_ADDRESS_ONE_NAME_DOB_MORTALITY_MATCH = 'ONE_NAME_ADDRESS_ONE_NAME_DOB_MORTALITY_MATCH'


class Field(StringType):
    GIVEN_NAMES = 'GIVEN_NAMES'
    FAMILY_NAME = 'FAMILY_NAME'
    DOB = 'DOB'
    ADDRESS_HISTORY = 'ADDRESS_HISTORY'


class CommercialRelationshipType(StringType, metaclass=EnumMeta):
    PASSFORT = 'PASSFORT'
    DIRECT = 'DIRECT'


class ErrorType(StringType, metaclass=EnumMeta):
    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    INVALID_CONFIG = 'INVALID_CONFIG'
    MISSING_CHECK_INPUT = 'MISSING_CHECK_INPUT'
    INVALID_CHECK_INPUT = 'INVALID_CHECK_INPUT'
    PROVIDER_CONNECTION = 'PROVIDER_CONNECTION'
    PROVIDER_MESSAGE = 'PROVIDER_MESSAGE'
    UNSUPPORTED_DEMO_RESULT = 'UNSUPPORTED_DEMO_RESULT'


class ErrorSubType(StringType, metaclass=EnumMeta):
    # INVALID_CHECK_INPUT
    UNSUPPORTED_COUNTRY = 'UNSUPPORTED_COUNTRY'


class EntityType(StringType, metaclass=EnumMeta):
    INDIVIDUAL = 'INDIVIDUAL'


class AddressType(StringType, metaclass=EnumMeta):
    STRUCTURED = 'STRUCTURED'


class GenderType(StringType, metaclass=EnumMeta):
    MALE = 'M'
    FEMALE = 'F'


class EkycDatabaseType(StringType, metaclass=EnumMeta):
    CIVIL = 'CIVIL'
    CREDIT = 'CREDIT'
    MORTALITY = 'MORTALITY'
    IGNORED = 'IGNORED'


class EkycMatchField(StringType, metaclass=EnumMeta):
    FORENAME = 'FORENAME'
    SURNAME = 'SURNAME'
    ADDRESS = 'ADDRESS'
    DOB = 'DOB'
    IDENTITY_NUMBER = 'IDENTITY_NUMBER'
    IDENTITY_NUMBER_SUFFIX = 'IDENTITY_NUMBER_SUFFIX'


class ProviderConfig(Model):
    require_dob = BooleanType(required=True)
    mortality_check = BooleanType(required=True)
    requires_address_on_all_matches = BooleanType(required=True)
    run_original_address = BooleanType(required=True)
    whitelisted_databases = ListType(StringType)


class ProviderCredentials(Model):
    username = StringType(required=True)
    password = StringType(required=True)
    url = StringType(required=True)
    public_key = StringType(required=True)
    private_key = StringType(required=True)


class Error(Model):
    type = ErrorType(required=True)
    sub_type = ErrorSubType()
    message = StringType(required=True)
    data = DictType(StringType(), default=None)

    @staticmethod
    def unsupported_country():
        return Error({
            'type': ErrorType.INVALID_CHECK_INPUT,
            'sub_type': ErrorSubType.UNSUPPORTED_COUNTRY,
            'message': 'Country not supported.',
        })

    @staticmethod
    def missing_required_field(field: str):
        return Error({
            'type': ErrorType.MISSING_CHECK_INPUT,
            'data': {
                'field': field,
            },
            'message': f'Missing required field ({field})',
        })

    class Options:
        export_level = NOT_NONE


class Warn(Model):
    type = ErrorType(required=True)
    message = StringType(required=True)

    class Options:
        export_level = NOT_NONE


class FullName(Model):
    title = StringType(default=None)
    given_names = ListType(StringType(), default=None)
    family_name = StringType(min_length=1, default=None)

    class Options:
        export_level = NOT_NONE


class PersonalDetails(Model):
    name: Optional[FullName] = ModelType(FullName, default=None)
    dob = StringType(default=None)
    nationality = StringType(default=None)
    national_identity_number = DictType(StringType(), default=None)
    gender = GenderType(default=None)

    class Options:
        export_level = NOT_NONE


class StructuredAddress(Model):
    country = StringType(required=True)
    state_province = StringType(default=None)
    county = StringType(default=None)
    postal_code = StringType(default=None)
    locality = StringType(default=None)
    postal_town = StringType(default=None)
    route = StringType(default=None)
    street_number = StringType(default=None)
    premise = StringType(default=None)
    subpremise = StringType(default=None)
    address_lines = ListType(StringType(), default=None)

    class Options:
        export_level = NOT_NONE


class Address(StructuredAddress):
    type = AddressType(required=True, default=AddressType.STRUCTURED)
    original_freeform_address = StringType(default=None)
    original_structured_address: Optional[StructuredAddress] = ModelType(
        StructuredAddress, default=None)


class DatedAddress(Model):
    address: Address = ModelType(Address, required=True)
    start_date = ApproxDateType(default=None)
    end_date = ApproxDateType(default=None)

    class Options:
        export_level = NOT_NONE


class EkycExtraField(Model):
    name = StringType(required=True)
    value = StringType(default=None)


class EkycMatch(Model):
    database_name = StringType(required=True)
    database_type = EkycDatabaseType(required=True)
    matched_fields = ListType(EkycMatchField, required=True)
    date_first_seen = DateType(default=None)
    date_of_last_activity = DateType(default=None)
    extra: Optional[EkycExtraField] = ListType(
        ModelType(EkycExtraField), default=None)
    count = IntType(required=True, min_value=0)

    class Options:
        export_level = NOT_NONE


class ContactDetails(Model):
    phone_number = StringType(default=None)

    class Options:
        export_level = NOT_NONE


class ElectronicIdCheck(Model):
    matches: Optional[EkycMatch] = ListType(ModelType(EkycMatch), default=None)
    provider_reference_number = StringType(default=None)

    class Options:
        export_level = NOT_NONE


class IndividualData(Model):
    entity_type = EntityType(required=True, default=EntityType.INDIVIDUAL)
    personal_details: Optional[PersonalDetails] = ModelType(
        PersonalDetails, default=None)
    address_history: Optional[List[DatedAddress]] = ListType(
        ModelType(DatedAddress), default=None)
    contact_details: Optional[ContactDetails] = ModelType(
        ContactDetails, default=None)
    electronic_id_check: Optional[ElectronicIdCheck] = ModelType(
        ElectronicIdCheck, default=None)

    class Options:
        export_level = NOT_NONE

    def get_current_address(self) -> Optional[Address]:
        if self.address_history:
            return self.address_history[-1].address
        else:
            return None

    def get_dob(self) -> Optional[str]:
        return self.personal_details and self.personal_details.dob

    def get_given_names(self) -> Optional[List[str]]:
        return self.personal_details and self.personal_details.name and self.personal_details.name.given_names

    def get_family_name(self) -> Optional[str]:
        return self.personal_details and self.personal_details.name and self.personal_details.name.family_name


class Charge(Model):
    amount = IntType(required=True)
    reference = StringType(default=None)
    sku = StringType(default=None)

    class Options:
        export_level = NOT_NONE


class RunCheckRequest(Model):
    id = UUIDType(required=True)
    demo_result = DemoResultType(default=None)
    commercial_relationship = CommercialRelationshipType(required=True)
    check_input: IndividualData = ModelType(IndividualData, required=True)
    provider_config: ProviderConfig = ModelType(ProviderConfig, required=True)
    provider_credentials: Optional[ProviderCredentials] = ModelType(
        ProviderCredentials, default=None)

    class Options:
        export_level = NOT_NONE


class RunCheckResponse(Model):
    check_output: Optional[IndividualData] = ModelType(
        IndividualData, default=None)
    errors: List[Error] = ListType(ModelType(Error), default=[])
    warnings: List[Warn] = ListType(ModelType(Warn), default=[])
    provider_data = BaseType(default=None)
    charges = ListType(ModelType(Charge), default=[])

    @staticmethod
    def error(errors: List[Error]) -> 'RunCheckResponse':
        res = RunCheckResponse()
        res.errors = errors
        return res


T = TypeVar('T')


def _first(x: Iterable[T]) -> Optional[T]:
    return next(iter(x), None)


def _get_input_annotation(signature: inspect.Signature) -> Optional[Type[Model]]:
    first_param: Optional[inspect.Parameter] = _first(
        signature.parameters.values())
    if first_param is None:
        return None

    if first_param.kind not in [inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD]:
        return None

    if not issubclass(first_param.annotation, Model):
        return None

    return first_param.annotation


def validate_models(fn):
    """
    Creates a Schematics Model from the request data and validates it.

    Throws DataError if invalid.
    Otherwise, it passes the validated request data to the wrapped function.
    """

    signature = inspect.signature(fn)

    assert issubclass(signature.return_annotation,
                      Model), 'Must have a return type annotation'
    output_model = signature.return_annotation
    input_model = _get_input_annotation(signature)

    @wraps(fn)
    def wrapped_fn(*args, **kwargs):
        if input_model is None:
            res = fn(*args, **kwargs)
        else:
            model = None
            try:
                model = input_model().import_data(request.json, apply_defaults=True)
                model.validate()
            except DataError as e:
                abort(Response(str(e), status=400))

            res = fn(model, *args, **kwargs)

        assert isinstance(res, output_model)

        return jsonify(res.serialize())

    return wrapped_fn

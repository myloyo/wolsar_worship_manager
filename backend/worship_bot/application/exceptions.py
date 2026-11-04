class ConsentRequiredError(ValueError):
    """Raised when a participant has not accepted the data processing consent."""


class ParticipantNotFoundError(LookupError):
    """Raised when a participant does not exist."""


class EventTypeNotFoundError(LookupError):
    """Raised when an event type does not exist."""


class EventNotFoundError(LookupError):
    """Raised when an event does not exist."""


class ChurchNotFoundError(LookupError):
    """Raised when a church does not exist."""


class ChurchAlreadyExistsError(ValueError):
    """Raised when a church with the same name already exists."""


class ChurchMinistryNotFoundError(LookupError):
    """Raised when a church-specific ministry does not exist."""


class MinistryRoleNotFoundError(LookupError):
    """Raised when a role does not belong to the requested ministry."""


class UserMinistryRoleNotFoundError(LookupError):
    """Raised when a user is not registered in the requested ministry role."""


class RoleAssignmentMismatchError(ValueError):
    """Raised when a participant's role does not match the event role slot."""


class EventRoleSlotNotFoundError(LookupError):
    """Raised when an event role slot does not exist."""


class EventInvitationNotFoundError(LookupError):
    """Raised when an invitation does not exist or is not owned by the caller."""


class EventInvitationStateError(ValueError):
    """Raised when an invitation cannot transition from its current state."""


class InvalidRecurrenceRuleError(ValueError):
    """Raised when an event recurrence rule is invalid or unbounded."""


class EventSongsNotAllowedError(ValueError):
    """Raised when songs are attached to an event outside the worship ministry."""


class EventSeriesValidationError(ValueError):
    """Raised when an event series request is internally inconsistent."""


class RegistrationDraftNotFoundError(LookupError):
    """Raised when a registration draft is missing or belongs to another identity."""


class RegistrationStepError(ValueError):
    """Raised when submitted answers do not match the current registration step."""


class ExternalAccountAlreadyLinkedError(ValueError):
    """Raised when a platform account is already linked to another profile."""


class MinistryTypeAlreadyExistsError(ValueError):
    """Raised when a global ministry name is already registered."""


class MinistryRoleAlreadyExistsError(ValueError):
    """Raised when a role name already exists in a church ministry."""


class AccessDeniedError(PermissionError):
    """Raised when the actor lacks permission for a ministry operation."""


class PlanningProviderError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code

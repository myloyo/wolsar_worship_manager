from enum import StrEnum


class WorshipRole(StrEnum):
    LEAD_VOCAL = "lead_vocal"
    BACK_VOCAL = "back_vocal"
    BACK_VOCAL_2 = "back_vocal_2"
    BACK_VOCAL_3 = "back_vocal_3"
    DRUMS = "drums"
    BASS = "bass"
    ELECTRIC_GUITAR = "electric_guitar"
    ELECTRIC_GUITAR_2 = "electric_guitar_2"
    ACOUSTIC_GUITAR = "acoustic_guitar"
    KEYS = "keys"
    VIOLIN = "violin"
    SOUND = "sound"
    SOUND_2 = "sound_2"
    DANCER = "dancer"


class SystemRole(StrEnum):
    MEMBER = "member"
    COORDINATOR = "coordinator"
    ADMIN = "admin"
    DEVELOPER = "developer"


class ConfirmationStatus(StrEnum):
    REPLACEMENT = "replacement"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"


class IdentityProvider(StrEnum):
    TELEGRAM = "telegram"
    VK = "vk"


class RegistrationStep(StrEnum):
    CHURCH = "church"
    NAME = "name"
    BIRTHDAY = "birthday"
    MINISTRIES = "ministries"
    ROLES = "roles"
    CONSENT = "consent"
    REVIEW = "review"
    COMPLETED = "completed"


class InvitationStatus(StrEnum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class NotificationStatus(StrEnum):
    CANCELLED = "cancelled"
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"

"""Config validation and generation for isolated ODJ demo staging.

No Stripe, SMTP, production database, or local .env is copied or activated.
Pure functions support offline tests; CLI handles private interactive input.
"""
import re
import secrets
from security import make_password_hash

_DOMAIN = re.compile(r'(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


def valid_hostname(hostname):
    return bool(_DOMAIN.fullmatch(str(hostname).lower().strip())) and not hostname.lower().endswith('.local')


def generate_staging_config(hostname, admin_password, staging_user, staging_password):
    hostname = hostname.lower().strip()
    if not valid_hostname(hostname):
        raise ValueError('Staging must use a real DNS hostname such as preview.example.com.')
    if not staging_user or ':' in staging_user or not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', staging_user):
        raise ValueError('Staging username must be 3-40 letters, digits, underscores, dots or hyphens.')
    if len(admin_password) < 12:
        raise ValueError('Admin password must be at least 12 characters.')
    if len(staging_password) < 20:
        raise ValueError('Separate staging site password must be at least 20 characters.')
    if staging_password == admin_password:
        raise ValueError('Admin and staging passwords must be different.')
    # Colon/newline/quotes/etc in .env cause ambiguity and unsafe interpolation.
    if not re.fullmatch(r'[A-Za-z0-9._!@%+=,;:?-]{20,128}', staging_password):
        raise ValueError('Staging password must use 20-128 safe characters (letters, digits, . _ ! @ % + = , ; : ? -).')
    options = {
        'APP_ENV': 'staging',
        'PAYMENT_MODE': 'demo',
        'DOMAIN': hostname,
        'PUBLIC_BASE_URL': 'https://' + hostname,
        'POSTGRES_PASSWORD': secrets.token_urlsafe(40),
        'SESSION_SECRET': secrets.token_urlsafe(48),
        'ADMIN_PASSWORD_HASH': make_password_hash(admin_password),
        'STAGING_ACCESS_USER': staging_user,
        'STAGING_ACCESS_PASSWORD': staging_password,
        'STRIPE_SECRET_KEY': '',
        'STRIPE_WEBHOOK_SECRET': '',
        'SMTP_HOST': '',
        'SMTP_USERNAME': '',
        'SMTP_PASSWORD': '',
        'SMTP_FROM': '',
    }
    return options


def validate_staging_config(config):
    """Return human-safe reasons (never include private values)."""
    errors = []
    hostname = config.get('DOMAIN', '').strip()
    if not valid_hostname(hostname):
        errors.append('Staging hostname is missing or malformed.')
    if config.get('APP_ENV') != 'staging' or config.get('PAYMENT_MODE') != 'demo':
        errors.append('Staging must use APP_ENV=staging and PAYMENT_MODE=demo.')
    if config.get('PUBLIC_BASE_URL') != 'https://' + hostname:
        errors.append('PUBLIC_BASE_URL must exactly match the staging HTTPS hostname.')
    if len(config.get('POSTGRES_PASSWORD', '')) < 32:
        errors.append('A unique, strong staging PostgreSQL password is required.')
    if len(config.get('SESSION_SECRET', '')) < 32:
        errors.append('Staging SESSION_SECRET is too short.')
    if not config.get('ADMIN_PASSWORD_HASH', '').startswith('pbkdf2_sha256$'):
        errors.append('Staging admin password hash is missing.')
    if len(config.get('STAGING_ACCESS_PASSWORD', '')) < 20 or not config.get('STAGING_ACCESS_USER'):
        errors.append('Separate staging access credentials are missing or weak.')
    for key in ('STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'):
        if config.get(key):
            errors.append('No Stripe credentials are permitted in this demo staging configuration.')
    for key in ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD'):
        if config.get(key):
            errors.append('Outbound email must remain disabled for this demo staging setup.')
    return errors


def render_env(config):
    """Escapes values for python-dotenv and Docker Compose variable interpolation.

    User-supplied fields are validated separately; generated secrets use URL-safe
    characters. Staging access password forbids shell-sensitive syntax.
    """
    errors = validate_staging_config(config)
    if errors:
        raise ValueError('; '.join(errors))
    for k, v in config.items():
        if any(c in str(v) for c in '\r\n') or not re.fullmatch(r'[A-Z][A-Z0-9_]*', k):
            raise ValueError('Invalid staging env content.')
    # Compose interpolates $ in unquoted env_file values. Single-quote the PBKDF2
    # hash so its dollar separators stay literal in both Compose and dotenv.
    lines = []
    for key, value in config.items():
        encoded = f"'{value}'" if key == 'ADMIN_PASSWORD_HASH' else value
        lines.append(f'{key}={encoded}\n')
    return '# PRIVATE ODJ V7.6 STAGING CREDENTIALS. DO NOT COMMIT.\n' + ''.join(lines)

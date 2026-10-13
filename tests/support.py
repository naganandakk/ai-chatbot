from backend.app.auth import ACCESS_COOKIE, TokenService

USER_ID = "user-1"
OTHER_USER_ID = "user-2"
TEST_SECRET = "test-secret-that-is-long-enough-for-hs256"


def sign_in(client, user_id: str = USER_ID):
    # Tests use a real signed token, so the auth check runs as it does in production
    token = TokenService(TEST_SECRET).issue_access_token(user_id)
    client.set_cookie(ACCESS_COOKIE, token)
    return client

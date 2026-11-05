from datetime import UTC, datetime


def utcnow() -> datetime:
    """DB 에 저장할 '지금' 시각.

    MongoDB 는 datetime 을 밀리초 단위로 저장한다. Python 의 datetime.now() 는 마이크로초까지 있어서,
    메모리의 값(…437318µs)과 DB 에서 다시 읽은 값(…437000µs)이 미세하게 달라진다.
    처음부터 밀리초로 잘라 두면 "넣은 값 == 읽은 값" 이 보장되어 비교·테스트가 단순해진다.
    """
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)

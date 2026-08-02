"""验证核心第三方包可导入。"""

def test_imports():
    import fastapi  # noqa
    import sqlalchemy  # noqa
    import claude_agent_sdk  # noqa
    import aiomysql  # noqa
    import dotenv  # noqa
    assert True

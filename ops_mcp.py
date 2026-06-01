from aliyun_ops_mcp import mcp


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)

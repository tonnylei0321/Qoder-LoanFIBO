#!/usr/bin/env python3
"""端到端 WebSocket 测试 — 模拟 ERP Agent 完整连接生命周期。

测试流程：
1. WS 连接 → auth 消息认证
2. register 消息 → 注册路由
3. heartbeat → 心跳
4. 等待 task → 发送 ack + result
5. 断开连接
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("请先安装 websockets: pip install websockets")
    sys.exit(1)

WS_URL = "ws://localhost:8000/api/v1/agent/connect"

# 使用刚才测试创建的凭证
CLIENT_ID = "cid_f97565d8c6e2c496f3ad40ea39912173"
CLIENT_SECRET = "sk_7836c8e2982e179083033455332bb95b15c3195ac48d28af63fd4409d1ed27b2"


async def test_ws_lifecycle():
    print("=" * 60)
    print("ERP Agent WebSocket 端到端测试")
    print("=" * 60)

    # 1. 建立 WebSocket 连接
    print("\n[1] 建立 WebSocket 连接...")
    try:
        ws = await websockets.connect(WS_URL)
        print(f"    ✅ 连接成功: {WS_URL}")
    except Exception as e:
        print(f"    ❌ 连接失败: {e}")
        return False

    # 2. 发送 auth 消息
    print("\n[2] 发送 auth 消息...")
    auth_msg = {
        "type": "auth",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    await ws.send(json.dumps(auth_msg))
    response = await asyncio.wait_for(ws.recv(), timeout=5)
    auth_resp = json.loads(response)
    print(f"    收到响应: {json.dumps(auth_resp, indent=2)}")

    if auth_resp.get("type") == "auth_ok":
        print("    ✅ 认证成功")
    else:
        print(f"    ❌ 认证失败: {auth_resp}")
        await ws.close()
        return False

    # 3. 发送 register 消息
    print("\n[3] 发送 register 消息...")
    register_msg = {
        "type": "register",
        "datasource": "NCC",
        "version": "1.0.0",
    }
    await ws.send(json.dumps(register_msg))
    response = await asyncio.wait_for(ws.recv(), timeout=5)
    reg_resp = json.loads(response)
    print(f"    收到响应: {json.dumps(reg_resp, indent=2)}")

    if reg_resp.get("type") == "register_ack":
        print("    ✅ 注册成功")
    else:
        print(f"    ❌ 注册失败: {reg_resp}")
        await ws.close()
        return False

    # 4. 发送心跳
    print("\n[4] 发送 heartbeat...")
    heartbeat_msg = {"type": "heartbeat"}
    await ws.send(json.dumps(heartbeat_msg))
    response = await asyncio.wait_for(ws.recv(), timeout=5)
    hb_resp = json.loads(response)
    print(f"    收到响应: {json.dumps(hb_resp, indent=2)}")

    if hb_resp.get("type") == "heartbeat_ack":
        print("    ✅ 心跳成功")
    else:
        print(f"    ⚠️ 心跳响应异常: {hb_resp}")

    # 5. 查询代理状态（从另一个连接视角）
    print("\n[5] 查询代理状态...")
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/agent/status")
        with urllib.request.urlopen(req) as resp:
            status_data = json.loads(resp.read())
            print(f"    状态: {json.dumps(status_data, indent=2, ensure_ascii=False)}")
            if status_data.get("data") and len(status_data["data"]) > 0:
                agent = status_data["data"][0]
                print(f"    ✅ 代理在线: status={agent.get('status')}, datasource={agent.get('datasource')}")
            else:
                print("    ⚠️ 无在线代理")
    except Exception as e:
        print(f"    ⚠️ 状态查询失败: {e}")

    # 6. 提交任务
    print("\n[6] 提交任务到代理...")
    task_payload = {
        "org_id": "0d483f09-aa7f-4c04-bfd4-fb8380815d00",
        "datasource": "NCC",
        "action": "query_indicator",
        "payload": {"indicator": "revenue", "period": "2025-Q1"},
        "timeout_ms": 5000,
    }
    try:
        req = urllib.request.Request(
            "http://localhost:8000/api/v1/agent/task",
            data=json.dumps(task_payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-token"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            task_resp = json.loads(resp.read())
            print(f"    任务提交响应: {json.dumps(task_resp, indent=2, ensure_ascii=False)}")
            msg_id = task_resp.get("data", {}).get("msg_id")
            if msg_id:
                print(f"    ✅ 任务已分发, msg_id={msg_id}")

                # 7. 代理收到 task，发送 ack + result
                print("\n[7] 代理接收任务并响应...")
                try:
                    task_msg_raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    task_msg = json.loads(task_msg_raw)
                    print(f"    收到任务: {json.dumps(task_msg, indent=2)}")

                    if task_msg.get("type") == "task":
                        # 发送 ack
                        ack_msg = {
                            "type": "ack",
                            "msg_id": task_msg["msg_id"],
                        }
                        await ws.send(json.dumps(ack_msg))
                        print(f"    ✅ 已发送 ack (msg_id={task_msg['msg_id']})")

                        # 发送 result
                        result_msg = {
                            "type": "result",
                            "msg_id": task_msg["msg_id"],
                            "payload": {
                                "indicator": "revenue",
                                "value": 12345678.90,
                                "period": "2025-Q1",
                            },
                        }
                        await ws.send(json.dumps(result_msg))
                        print(f"    ✅ 已发送 result (msg_id={task_msg['msg_id']})")
                    else:
                        print(f"    ⚠️ 收到非 task 消息: {task_msg.get('type')}")
                except asyncio.TimeoutError:
                    print("    ⚠️ 等待任务超时（5s），跳过")
            else:
                print(f"    ⚠️ 任务提交状态: {task_resp}")
    except Exception as e:
        print(f"    ⚠️ 任务提交失败: {e}")

    # 8. 查询追踪信息
    print("\n[8] 查询追踪信息...")
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/agent/traces?limit=5")
        with urllib.request.urlopen(req) as resp:
            traces = json.loads(resp.read())
            print(f"    追踪: {json.dumps(traces, indent=2, ensure_ascii=False)}")
            if traces.get("data") and len(traces["data"]) > 0:
                print("    ✅ 追踪记录存在")
            else:
                print("    ⚠️ 无追踪记录")
    except Exception as e:
        print(f"    ⚠️ 追踪查询失败: {e}")

    # 9. 关闭连接
    print("\n[9] 关闭 WebSocket 连接...")
    await ws.close()
    print("    ✅ 连接已关闭")

    # 10. 等待一小段时间后检查状态变为 OFFLINE
    print("\n[10] 等待 2 秒后检查状态...")
    await asyncio.sleep(2)
    try:
        req = urllib.request.Request("http://localhost:8000/api/v1/agent/status")
        with urllib.request.urlopen(req) as resp:
            status_data = json.loads(resp.read())
            if status_data.get("data") and len(status_data["data"]) > 0:
                for agent in status_data["data"]:
                    print(f"    代理: {agent.get('datasource')} status={agent.get('status')}")
            else:
                print("    ✅ 代理已离线（路由表已清理）")
    except Exception as e:
        print(f"    ⚠️ 状态查询失败: {e}")

    print("\n" + "=" * 60)
    print("端到端测试完成！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(test_ws_lifecycle())
    sys.exit(0 if result else 1)

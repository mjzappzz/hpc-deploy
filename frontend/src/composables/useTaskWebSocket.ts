/**
 * WebSocket hook for real-time task log streaming.
 *
 * Usage:
 *   const { connect, disconnect, isConnected, wsError } = useTaskWebSocket()
 *   connect('task-xxx', onLog, onStatus, onDone)
 *
 * Auto-fallback to HTTP polling on connection failure.
 */

import { ref } from 'vue'

export interface WsLogMessage {
  type: 'log'
  task_id: string
  level: string
  line: string
  created_at?: string
}

export interface WsStatusMessage {
  type: 'status'
  task_id: string
  status: string
}

export interface WsDoneMessage {
  type: 'done'
  task_id: string
  status: string
}

export interface WsErrorMessage {
  type: 'error'
  message: string
}

export type WsMessage = WsLogMessage | WsStatusMessage | WsDoneMessage | WsErrorMessage

export type OnLogCallback = (level: string, line: string, created_at?: string) => void
export type OnStatusCallback = (status: string) => void
export type OnDoneCallback = (status: string) => void

export function useTaskWebSocket() {
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let closed = false

  const isConnected = ref(false)
  const wsError = ref<string | null>(null)

  function buildWsUrl(taskId: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host  // 保留当前访问端口；生产 Nginx 与开发 Vite 均可代理 WebSocket
    return `${protocol}//${host}/api/tasks/${taskId}/logs/ws`
  }

  function connect(
    taskId: string,
    onLog: OnLogCallback,
    onStatus: OnStatusCallback,
    onDone: OnDoneCallback,
  ) {
    closed = false
    wsError.value = null

    try {
      const url = buildWsUrl(taskId)
      ws = new WebSocket(url)

      ws.onopen = () => {
        isConnected.value = true
        wsError.value = null
        // Heartbeat ping every 30s
        heartbeatTimer = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 30000)
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: WsMessage = JSON.parse(event.data)
          switch (msg.type) {
            case 'log':
              onLog(msg.level, msg.line, msg.created_at)
              break
            case 'status':
              onStatus(msg.status)
              break
            case 'done':
              onDone(msg.status)
              // Keep socket open a moment for any final messages, then close
              break
            case 'error':
              wsError.value = msg.message
              break
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onerror = () => {
        wsError.value = 'WebSocket 连接失败'
        isConnected.value = false
      }

      ws.onclose = () => {
        isConnected.value = false
        cleanup()
      }
    } catch {
      wsError.value = 'WebSocket 连接失败'
      isConnected.value = false
    }
  }

  function disconnect() {
    closed = true
    cleanup()
    if (ws) {
      ws.close()
      ws = null
    }
  }

  function cleanup() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function getIsConnected() {
    return isConnected.value
  }

  function getWsError() {
    return wsError.value
  }

  return {
    connect,
    disconnect,
    isConnected,
    wsError,
    getIsConnected,
    getWsError,
  }
}

/** WebSocket Composable for Job Progress */
import { ref, onUnmounted } from 'vue'
import type { JobProgress } from '@/types'

export function useJobWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const lastProgress = ref<JobProgress | null>(null)
  const error = ref<string | null>(null)

  const connect = (jobId: number) => {
    // Close existing connection
    disconnect()

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/jobs/${jobId}`
    
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      isConnected.value = true
      error.value = null
      console.log(`WebSocket connected for job ${jobId}`)
    }

    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as JobProgress
        lastProgress.value = data
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.value.onerror = (e) => {
      error.value = 'WebSocket error occurred'
      console.error('WebSocket error:', e)
    }

    ws.value.onclose = () => {
      isConnected.value = false
      console.log(`WebSocket disconnected for job ${jobId}`)
    }
  }

  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
      isConnected.value = false
    }
  }

  // Auto disconnect on component unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    lastProgress,
    error,
    connect,
    disconnect,
  }
}

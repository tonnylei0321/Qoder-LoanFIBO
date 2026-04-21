<template>
  <span class="alert-badge" :class="level">
    <span class="dot"></span>
    <span class="text">{{ labelMap[level] }}</span>
  </span>
</template>

<script setup lang="ts">
defineProps<{
  level: 'normal' | 'warning' | 'alert'
}>()

const labelMap = {
  normal: '正常',
  warning: '关注',
  alert: '预警',
}
</script>

<style scoped>
.alert-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

/* Normal */
.alert-badge.normal {
  background: rgba(16, 185, 129, 0.12);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}
.alert-badge.normal .dot {
  background: #10b981;
  box-shadow: 0 0 4px #10b981;
}

/* Warning */
.alert-badge.warning {
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.alert-badge.warning .dot {
  background: #f59e0b;
  box-shadow: 0 0 4px #f59e0b;
  animation: pulse 1.5s ease-in-out infinite;
}

/* Alert */
.alert-badge.alert {
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.alert-badge.alert .dot {
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}
</style>

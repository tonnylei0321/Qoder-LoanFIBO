<template>
  <div class="jobs">
    <div class="page-header">
      <h1>任务管理</h1>
      <el-button type="primary" @click="$router.push('/jobs/new')">
        <el-icon><Plus /></el-icon>
        新建任务
      </el-button>
    </div>

    <el-card>
      <el-table :data="jobs" v-loading="loading" stripe>
        <el-table-column prop="id" label="任务ID" width="80" />
        <el-table-column prop="name" label="任务名称" min-width="180" />
        <el-table-column prop="ddlFileTag" label="DDL源" width="150" />
        <el-table-column prop="ttlFileTag" label="目标本体" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :status="getProgressStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewJob(row)">
              查看
            </el-button>
            <el-button
              v-if="row.status === 'running'"
              type="warning"
              link
              size="small"
              @click="pauseJob(row)"
            >
              暂停
            </el-button>
            <el-button
              v-if="row.status === 'paused'"
              type="success"
              link
              size="small"
              @click="resumeJob(row)"
            >
              恢复
            </el-button>
            <el-button
              v-if="['running', 'paused'].includes(row.status)"
              type="danger"
              link
              size="small"
              @click="stopJob(row)"
            >
              停止
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadJobs"
          @current-change="loadJobs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { jobsApi } from '@/api'
import type { Job } from '@/types'

const router = useRouter()
const loading = ref(false)
const jobs = ref<Job[]>([])

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'primary',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    stopped: 'info',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待启动',
    running: '运行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止',
  }
  return map[status] || status
}

const getProgressStatus = (row: Job) => {
  if (row.status === 'completed') return 'success'
  if (row.status === 'failed') return 'exception'
  return undefined
}

const loadJobs = async () => {
  loading.value = true
  try {
    const res = await jobsApi.getJobs({
      page: pagination.page,
      pageSize: pagination.pageSize,
    })
    jobs.value = res.items
    pagination.total = res.total
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

const viewJob = (row: Job) => {
  router.push(`/dashboard/job/${row.id}`)
}

const pauseJob = async (row: Job) => {
  try {
    await jobsApi.pauseJob(row.id)
    ElMessage.success('任务已暂停')
    loadJobs()
  } catch (error) {
    ElMessage.error('暂停失败')
  }
}

const resumeJob = async (row: Job) => {
  try {
    await jobsApi.resumeJob(row.id)
    ElMessage.success('任务已恢复')
    loadJobs()
  } catch (error) {
    ElMessage.error('恢复失败')
  }
}

const stopJob = async (row: Job) => {
  try {
    await jobsApi.stopJob(row.id)
    ElMessage.success('任务已停止')
    loadJobs()
  } catch (error) {
    ElMessage.error('停止失败')
  }
}

onMounted(() => {
  loadJobs()
})
</script>

<style scoped>
.jobs {
  padding-bottom: 40px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>

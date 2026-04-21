import request from './request'

export interface ReviewComment {
  id: number
  issue_type: string
  severity: string
  is_must_fix: boolean
  issue_description: string
  suggested_fix: string | null
  review_round: number
  created_at: string | null
}

export interface FieldMappingItem {
  id: number
  field_name: string
  field_type: string | null
  fibo_property_uri: string | null
  confidence_level: string | null
  mapping_reason: string | null
}

export interface ReviewItem {
  id: number
  job_id: number
  database_name: string
  table_name: string
  fibo_class_uri: string | null
  confidence_level: string | null
  mapping_reason: string | null
  mapping_status: string
  review_status: string
  revision_count: number
  model_used: string | null
  created_at: string | null
  updated_at: string | null
  reviews: ReviewComment[]
  field_mappings: FieldMappingItem[]
}

export interface ReviewListResult {
  items: ReviewItem[]
  total: number
  page: number
  page_size: number
}

export interface SubmitReviewPayload {
  action: 'approve' | 'reject'
  comment?: string
  new_fibo_class_uri?: string
}

export const reviewsApi = {
  /** 获取待审核/已审核列表 */
  getReviews(params?: {
    review_status?: string
    database?: string
    page?: number
    page_size?: number
  }): Promise<ReviewListResult> {
    return request.get('/pipeline/mappings/reviews', { params })
  },

  /** 提交审核决策 */
  submitReview(tableMappingId: number, payload: SubmitReviewPayload): Promise<{ review_status: string }> {
    return request.post(`/pipeline/mappings/${tableMappingId}/review`, payload)
  },
}

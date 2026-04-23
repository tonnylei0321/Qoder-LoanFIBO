/** Loan Analysis API */
import request from './request'

export interface Company {
  id: string
  name: string
  unified_code?: string
  industry?: string
  region?: string
  reg_tags: Record<string, boolean>
  created_at: string
}

export interface CompanyListResult {
  items: Company[]
  total: number
  page: number
  page_size: number
}

export interface DimensionDef {
  id: string
  code: string
  name: string
  weight: number
  scenario: string
  sort_order: number
}

export interface IndicatorDef {
  id: string
  code: string
  name: string
  fibo_path?: string
  formula?: string
  data_source?: string
  unit?: string
  dimension_id?: string
  scenario: string
  weight?: number
  threshold_warning?: number
  threshold_alert?: number
  threshold_direction: string
}

export interface IndicatorValue {
  id: string
  company_id: string
  indicator_id: string
  value?: number
  value_prev?: number
  change_pct?: number
  alert_level: 'normal' | 'warning' | 'alert'
  data_quality?: string
  calc_date: string
  // Enriched
  indicator_name?: string
  indicator_code?: string
  unit?: string
  fibo_path?: string
  formula?: string
  data_source?: string
  threshold_warning?: number
  threshold_alert?: number
  threshold_direction?: string
  dimension_code?: string
  dimension_name?: string
}

export interface DimensionScore {
  name: string
  score: number
  weight: number
  indicator_count: number
  normal_count: number
  warning_count: number
  alert_count: number
}

export interface ScoreRecord {
  id: string
  company_id: string
  scenario: string
  total_score?: number
  risk_level?: string
  dimension_scores: Record<string, DimensionScore>
  suggestion?: string
  calc_date: string
  created_at: string
}

export interface AlertSummary {
  normal: number
  warning: number
  alert: number
}

export interface CompanyScoreResponse {
  company: Company
  score_record?: ScoreRecord
  alert_summary: AlertSummary
  calc_date: string
}

export interface AlertRecord {
  id: string
  company_id: string
  indicator_id: string
  alert_level: 'warning' | 'alert'
  trigger_value?: number
  threshold_value?: number
  trigger_date: string
  action_suggestion?: string
  status: 'open' | 'resolved'
  created_at: string
  indicator_name?: string
  indicator_code?: string
  unit?: string
}

export interface CalculateResult {
  total_score?: number
  risk_level?: string
  alert_count: number
}

// ─── API calls ────────────────────────────────────────────────────

export const loanAnalysisApi = {
  // Companies
  getCompanies: (params?: { page?: number; page_size?: number; search?: string }): Promise<CompanyListResult> =>
    request.get('/loan-analysis/companies', { params }),

  getCompany: (id: string): Promise<Company> =>
    request.get(`/loan-analysis/companies/${id}`),

  createCompany: (data: Partial<Company>): Promise<Company> =>
    request.post('/loan-analysis/companies', data),

  updateCompany: (id: string, data: Partial<Company>): Promise<Company> =>
    request.patch(`/loan-analysis/companies/${id}`, data),

  // Dimensions & Indicators
  getDimensions: (scenario?: string): Promise<DimensionDef[]> =>
    request.get('/loan-analysis/dimensions', { params: scenario ? { scenario } : {} }),

  getIndicators: (scenario?: string): Promise<IndicatorDef[]> =>
    request.get('/loan-analysis/indicators', { params: scenario ? { scenario } : {} }),

  getIndicator: (id: string): Promise<IndicatorDef> =>
    request.get(`/loan-analysis/indicators/${id}`),

  // Indicator values
  getCompanyIndicators: (
    companyId: string,
    scenario: string,
    calcDate?: string,
  ): Promise<IndicatorValue[]> =>
    request.get(`/loan-analysis/companies/${companyId}/indicators`, {
      params: { scenario, calc_date: calcDate },
    }),

  // Score
  getCompanyScore: (
    companyId: string,
    scenario: string,
    calcDate?: string,
  ): Promise<CompanyScoreResponse> =>
    request.get(`/loan-analysis/companies/${companyId}/score`, {
      params: { scenario, calc_date: calcDate },
    }),

  // Calculate
  calculate: (
    companyId: string,
    scenario: string,
    calcDate: string,
  ): Promise<CalculateResult> =>
    request.post(`/loan-analysis/companies/${companyId}/calculate`, {
      scenario,
      calc_date: calcDate,
    }),

  // Alerts
  getAlerts: (
    companyId: string,
    scenario?: string,
    status?: string,
  ): Promise<AlertRecord[]> =>
    request.get(`/loan-analysis/companies/${companyId}/alerts`, {
      params: { scenario, status },
    }),

  // Indicator History Trend
  getIndicatorHistory: (
    companyId: string,
    indicatorId: string,
    params?: { start_date?: string; end_date?: string; limit?: number },
  ): Promise<IndicatorValue[]> =>
    request.get(`/loan-analysis/companies/${companyId}/indicators/${indicatorId}/history`, { params }),

  // Write indicator values with history (dual-write)
  writeIndicatorValuesWithHistory: (
    companyId: string,
    calcDate: string,
    values: Array<{ indicator_id: string; value?: number; value_prev?: number; data_quality?: string }>,
    source: string = 'manual',
  ): Promise<{ history_count: number; upserted_count: number; batch_id: string }> =>
    request.post(`/loan-analysis/companies/${companyId}/values/history?source=${source}`, {
      calc_date: calcDate,
      values,
    }),
}

export type QuestionOption = { label: string; description: string }

export type AnswerMode = 'manual' | 'auto'

// 'resolved' 는 항목을 고르지 않았는데 대화나 작업으로 해소된 질문이다. answer 에 사유를 적는다.
// 'dismissed' 는 사람이 질문이 아니라고 닫은 항목이다. '' 은 아직 답이 없다.
export type AnsweredBy = '' | AnswerMode | 'resolved' | 'dismissed'

export type PendingQuestion = {
  id: string
  question: string
  header: string
  detail: string
  // 권장 항목이 앞에 온다. 1개면 서술형 질문이고 그 1개가 권장 답변이다.
  options: QuestionOption[]
  recommended: string[]
  // 응답이 직접 권장했으면 true. false 면 recommended 는 추출 모델이 고른 값이고 auto 가 보내지 않는다.
  isRecommendationStated: boolean
  isMultiSelect: boolean
  answeredBy: AnsweredBy
  answer: string
  isDelivered: boolean
}

// 추출이 끝나기 전의 응답. 파일에 먼저 적어 비정상 종료 뒤 다시 추출한다.
// isRescan 은 사람이 Rescan 으로 다시 읽게 한 응답이다.
export type UnreadResponse = {
  prompt: string
  work: string
  text: string
  attempts: number
  isRescan?: true
}

// 답하기 전의 체크와 입력.
export type QuestionDraft = { picks: string[]; text: string }

export type Drafts = Record<string, QuestionDraft>

export type QuestionLog = {
  version: 1
  seq: number
  cwd: string
  mode: AnswerMode
  autoChain: number
  items: PendingQuestion[]
  unread: UnreadResponse[]
}

export type OtherSession = { sessionId: string; openCount: number }

declare module 'claude-code' {
  interface PluginState {
    'pending-questions': {
      log: Shaped<QuestionLog>
      others: Shaped<OtherSession[]>
      drafts: Shaped<Drafts>
    }
  }
}

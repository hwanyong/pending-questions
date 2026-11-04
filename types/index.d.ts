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
  // 질문과 권장 항목을 응답 본문에서 대조했으면 true. false 면 auto 가 보내지 않는다.
  isRecommendationStated: boolean
  // 응답에서 이 질문을 묻는 문장 전체. auto 답을 보낼 때 question 대신 쓴다. 판정을 통과하지 못하면 '' 이다.
  askedQuote: string
  // 이 판정을 낸 조건의 버전. register.tsx 의 AUTO_CHECK_VERSION 과 다르면 판정을 믿지 않는다.
  autoCheckVersion: number
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
    }
  }
}

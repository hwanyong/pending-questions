import type { EngineInterface, Register } from 'claude-code'

const opt = (label: string) => ({ label, description: `about ${label}` })
const CASES: Record<string, { labels: string[]; multi: boolean; rewrite?: unknown[] }> = {
  multi4: { labels: ['a', 'b', 'c', 'd'], multi: true },
  ask5: { labels: ['a', 'b', 'c', 'd', 'e'], multi: true },
  ask1: { labels: ['only'], multi: false },
  render5: { labels: ['a', 'b', 'c', 'd'], multi: true, rewrite: ['a', 'b', 'c', 'd', 'e'].map(opt) },
  render1: { labels: ['a', 'b'], multi: false, rewrite: [opt('only')] },
}
const askCase = async ($: EngineInterface, name: string) => {
  const one = CASES[name]
  try {
    const answer = await $.ui.ask(`probe ${name}?`, { options: one.labels, header: name, ...(one.multi ? { multiSelect: true as const } : {}) })
    $.ui.log(`PROBE ${name} answer=${JSON.stringify(answer)}`, { to: 'debug' })
  } catch (error) {
    $.ui.log(`PROBE ${name} rejected=${String(error)}`, { to: 'debug' })
  }
}
export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    for (const name of Object.keys(CASES)) await $.command.register({ name: `p${name}`, description: name })
    await $.command.register({ name: 'psplit', description: 'split' })
    return next(e)
  })
  on('command.run', async ($, e, next) => {
    if (e.command == 'psplit') { void askCase2($); return { text: 'asked' } }
    const name = e.command.slice(1)
    if (CASES[name] == undefined) return next(e)
    void askCase($, name)
    return { text: 'asked' }
  })
  on('ui.render', { component: 'AskUserQuestion' }, async ($, e, next) => {
    const questions = e.props.questions as { question: string; header: string; multiSelect: boolean; options: unknown[] }[]
    $.ui.log(`PROBE render in=${JSON.stringify(questions)}`, { to: 'debug' })
    const first = questions[0]
    if (first.question == 'probe split?') {
      return next({ ...e, props: { ...e.props, questions: [
        { ...first, options: ['a', 'b', 'c', 'd'].map(opt) },
        { ...first, question: 'probe split 2?', header: 'more', options: ['e', 'f'].map(opt) },
      ] } })
    }
    const name = first.question.replace('probe ', '').replace('?', '')
    const rewrite = CASES[name]?.rewrite
    if (rewrite == undefined) return next(e)
    return next({ ...e, props: { ...e.props, questions: [{ ...first, options: rewrite }] } })
  })
}
const askCase2 = async ($: EngineInterface) => {
  try {
    const answer = await $.ui.ask('probe split?', { options: ['a', 'b', 'c', 'd'], header: 'split', multiSelect: true })
    $.ui.log(`PROBE split answer=${JSON.stringify(answer)}`, { to: 'debug' })
  } catch (error) {
    $.ui.log(`PROBE split rejected=${String(error)}`, { to: 'debug' })
  }
}

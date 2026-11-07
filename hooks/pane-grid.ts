import type { EngineInterface, RenderElement, RenderNode } from 'claude-code'

// pane-grid 규약 읽기(plugin-pane-grid 저장소 docs/grid-and-tabs.md §3.3 · §3.5).
// usage-gauge · uhd-kanban(skill-kanban 저장소) 의 hooks/pane-grid.ts 에 같은 이름의 함수가 같은 본문으로 있다. 고치면 세 곳을 함께 고친다.
// pane-grid 의 state 타입은 그 저장소에만 있으므로(결정 9) 읽은 값을 실행 중에 검사한다.
// pane-grid 가 없으면 값이 undefined 이고, 이 mod 는 지금처럼 자기 pane 에 그린다.

const GRID_LAYOUT = { plugin: 'pane-grid', key: 'layout' } as const
const GRID_VERSION = 1

// tab: 칸이 든 배치의 이름. requestId: 그 배치의 grid pane id(`grid-<tab>`). columns · rows: 칸 안에 그릴 크기.
type GridPlacement = { tab: string; requestId: string; cell: string; columns: number; rows: number }

const isPlacement = (value: unknown): value is GridPlacement => {
  if (typeof value != 'object' || value == null) return false
  const placement = value as Record<string, unknown>
  return typeof placement.tab == 'string' && typeof placement.requestId == 'string'
    && typeof placement.columns == 'number' && typeof placement.rows == 'number'
}

// pane-grid 의 layout 값에서 이 mod 의 칸을 찾는다. `state.set` hook 의 `e.value` · `e.previous` 에도 쓴다.
export const placementIn = (layout: unknown, plugin: string): GridPlacement | undefined => {
  if (typeof layout != 'object' || layout == null) return undefined
  const { version, placed } = layout as { version?: unknown; placed?: unknown }
  if (version != GRID_VERSION || typeof placed != 'object' || placed == null) return undefined
  const placement = (placed as Record<string, unknown>)[plugin]
  return isPlacement(placement) ? placement : undefined
}

// 아래 함수는 화살표 함수가 아니라 function 선언이다. `claude plugin validate` 는 import 너머로는 function 선언으로만 $ 를 따라간다.

// 이 mod 를 넣은 칸. render 중에 부르면 pane-grid 가 배치를 바꿀 때 다시 그려진다.
export async function readPlacement($: EngineInterface, plugin: string): Promise<GridPlacement | undefined> {
  const read = await $.state.get(GRID_LAYOUT as never) as { value?: unknown }
  return placementIn(read.value, plugin)
}

// 로드 순서와 무관하게 칸에 그린다(plugin-pane-grid 저장소 docs/grid-and-tabs.md §3.5).
// 이 mod 가 pane-grid 뒤에 로드되면 next(e) 에 pane-grid 의 그림이 없으므로 `cell:<plugin>` Box 를 그 뒤에 덧붙이고, pane-grid 가 거둔다.
// 앞에 로드되면 next(e) 가 pane-grid 의 그림이므로 fillSlot 이 pane-grid 가 그린 `slot:<plugin>` Box 를 이 칸으로 채우고,
// offerChoice 가 빈 칸의 `choices:<cell>` Box 에 이 mod 의 Button 을 더한다. 그 누름은 pane-grid 의 ui.press hook 이 key 로 받는다.
const SLOT_KEY = 'slot:'
const CHOICES_KEY = 'choices:'
const ACTIVE_SUFFIX = ':active'
const NONE_KEY = 'none:'
const PLACE_KEY = 'place:'
// 빈 칸 선택지의 hotkey 1-9 는 활성 칸에서만 붙는다.
const CHOICE_HOTKEYS = 9

// offerChoice 가 Button 을 만들 때 넘기는 값. 누름은 pane-grid 가 받으므로 onPress 는 아무것도 하지 않는다.
type GridChoice = { key: string; label: string; hotkey?: string }

const keyOf = (node: RenderNode) => {
  if (typeof node == 'string') return undefined
  const props: Record<string, unknown> | undefined = 'props' in node ? node.props : undefined
  const key = props?.key
  return typeof key == 'string' ? key : undefined
}

const childrenOf = (node: RenderElement): readonly RenderNode[] => ('children' in node && Array.isArray(node.children) ? node.children : [])

// change 가 바꾼 노드까지의 경로만 복사한다. next(e) 가 준 그림은 frozen 이다.
const rewrite = (element: RenderElement, change: (element: RenderElement) => RenderElement | undefined): RenderElement => {
  const changed = change(element)
  if (changed) return changed
  const children = childrenOf(element)
  const rewritten = children.map(child => (typeof child == 'string' ? child : rewrite(child, change)))
  return rewritten.every((child, index) => child === children[index]) ? element : ({ ...element, children: rewritten } as RenderElement)
}

// pane-grid 가 이 mod 몫으로 그린 slot 에 cell 을 넣는다. next(e) 에 그 slot 이 없으면(이 mod 가 pane-grid 뒤에 로드됨) undefined 이고,
// 그때는 cell 을 next(e) 뒤에 덧붙인다.
export const fillSlot = (below: RenderElement, plugin: string, cell: RenderElement): RenderElement | undefined => {
  let isFilled = false
  const filled = rewrite(below, element => {
    if (keyOf(element) != `${SLOT_KEY}${plugin}`) return undefined
    isFilled = true
    return { ...element, children: [cell] } as RenderElement
  })
  return isFilled ? filled : undefined
}

// pane-grid 가 그린 빈 칸의 선택지마다 이 mod 의 Button 을 더한다. 선택지가 없으면 그대로 돌려준다.
// placement 가 있으면 이 mod 가 이미 놓인 칸이고, 누르면 그 칸에서 옮겨 온다는 것을 label 에 적는다.
export const offerChoice = (below: RenderElement, plugin: string, placement: GridPlacement | undefined, makeButton: (choice: GridChoice) => RenderElement): RenderElement =>
  rewrite(below, element => {
    const key = keyOf(element)
    if (!key?.startsWith(CHOICES_KEY)) return undefined
    const isActive = key.endsWith(ACTIVE_SUFFIX)
    const cell = key.slice(CHOICES_KEY.length, isActive ? -ACTIVE_SUFFIX.length : undefined)
    const choiceKey = `${PLACE_KEY}${cell}:${plugin}`
    const children = childrenOf(element).filter(child => !keyOf(child)?.startsWith(NONE_KEY))
    if (children.some(child => keyOf(child) == choiceKey)) return undefined
    const count = children.filter(child => keyOf(child)?.startsWith(PLACE_KEY)).length
    const hotkey = isActive && count < CHOICE_HOTKEYS ? String(count + 1) : undefined
    const label = placement ? `${plugin} (move from ${placement.cell})` : plugin
    return { ...element, children: [...children, makeButton({ key: choiceKey, label, hotkey })] } as RenderElement
  })

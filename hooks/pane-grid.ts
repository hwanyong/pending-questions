import type { EngineInterface } from 'claude-code'

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


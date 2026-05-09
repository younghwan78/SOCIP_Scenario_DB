# Phase 4 Discussion Log

**Date:** 2026-05-10
**Phase:** 04 — Level 0 Viewer DB

---

## Area 1: Streamlit-DB 연결 방식

**Q: Dashboard에서 ViewResponse를 어떻게 얻을까요?**
- 옵션: (A) service.py 직접 import / (B) HTTP API 호출
- **결정:** HTTP API 호출 (`requests.get()`)

**Q: API Base URL은 어떻게 설정?**
- **결정:** `st.sidebar` text input (default: `http://localhost:8000`)

**Q: Scenario/Variant 선택 UI?**
- **결정:** Sidebar dropdown — `/api/v1/scenarios` API에서 목록 조회, `st.cache_data(ttl=60)` 적용

---

## Area 2: Architecture mode 노드 배치

**발견된 문제:** pipeline YAML의 `nodes`에 `lane_id`, `stage`, `layer` 필드 없음
- 실제 YAML: `{id, ip_ref, instance_index, role}` 만 존재

**Q: 노드 위치를 어떻게 배치할까요?**
- **결정:** `ip_ref → IpCatalog.category → lane` 자동 매핑 (auto-grid)
- Stage: pipeline.edges topological sort에서 자동 도출

**Q: SW 스택(App/Framework) 포함 여부?**
- **결정:** HW IP만 — architecture mode에서는 App/Framework 레인 없음

---

## Area 3: Topology mode 데이터 소스

**Q: SW stack 데이터를 어디서 가져올까요?**
- 옵션: (A) view_projection에서 SW ORM 조회 / (B) pipeline YAML에 sw_stack 섹션 추가
- **결정:** pipeline YAML에 `sw_stack` 섹션 추가 (향후 perfetto에서 자동 생성)

**Q: Topology vs Gate overlay 우선순위?**
- **결정:** Topology mode 우선 (VIEW-03 → VIEW-04)

**도메인 insight (사용자 설명):**
> "SW가 중요한 부분은 실제 구현 범위안에 들어가는 HAL, kernel driver이고 이게 필요한
> 부분은 HW 동작 사이에 SW 동작이 필요하고 SW 동작이 끝나야 HW가 수행되기 때문에
> 실제 HW 동작 시간에 jitter가 생겨 성능 이슈가 있을 수 있기 때문.
> topology가 실제로 도움이 되고 그 다음에는 자세한 timing diagram인데
> 제대로 도움이 되려면 perfetto profiling 수준이 되어야 함"

핵심: M2M 경계에서 HAL ioctl + kernel interrupt → HW 시작 전 SW overhead → jitter 유발

---

## Area 4: Gate overlay 연동

**Q: GateExecutionResult를 뷰어에 어떻게 표시할까요?**
- **결정:** 노드 위에 직접 (색상/테두리로 status 구분)

**Q: Gate 데이터를 언제 fetch할까요?**
- **결정:** "Show Gate Status" 토글 ON 시에만 (lazy fetch)

---

## 사용자 추가 코멘트

> "다양한 scenario에도 일관된 품질의 diagram을 보여주는 viewer 필요.
> 결국 L0 viewer 기반으로 level 1, 2 확장되기 때문에 처음 결정이 중요"

→ 플랜 방향: 하드코딩 최소화, category 기반 auto-layout으로 임의 scenario 지원

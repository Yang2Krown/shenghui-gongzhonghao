const currentScrollTop = () => (
  window.scrollY
  || document.scrollingElement?.scrollTop
  || document.documentElement.scrollTop
  || document.body.scrollTop
  || 0
)

const restoreScrollTop = (scrollTop) => {
  const restore = () => {
    if (document.scrollingElement) document.scrollingElement.scrollTop = scrollTop
    document.documentElement.scrollTop = scrollTop
    document.body.scrollTop = scrollTop
    window.scrollTo({ left: 0, top: scrollTop, behavior: 'auto' })
  }
  restore()
  if (typeof window.requestAnimationFrame === 'function') window.requestAnimationFrame(restore)
}

/**
 * Keep the document at the same position while an Element Plus dialog opens
 * or closes. Dialogs opt out of Element Plus' body lock because this app keeps
 * the document scrollbar mounted; the overlay still prevents normal clicks
 * through to the page, while this helper prevents the browser from resetting
 * the page to the top during the transition.
 */
export function useDialogScrollPosition() {
  let scrollTop = 0
  const rememberDialogScroll = () => {
    scrollTop = currentScrollTop()
  }
  const restoreDialogScroll = () => restoreScrollTop(scrollTop)
  return { rememberDialogScroll, restoreDialogScroll }
}

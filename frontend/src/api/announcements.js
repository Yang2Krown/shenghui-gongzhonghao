import { get, post } from './api'

export const getActiveAnnouncements = () => get('/announcements/active')
export const dismissAnnouncement = (announcementId) => post('/announcements/dismiss', { announcement_id: announcementId })

import type { ChildProfileView, PetProfileView } from '../api'

export function ageBandLabel(band: string) {
  return ({ '0-6m': '0-6 个月', '6-12m': '6-12 个月', '1-3y': '1-3 岁', '3-6y': '3-6 岁' } as Record<string, string>)[band] || band
}

export function genderLabel(gender: string | null) {
  return ({ male: '男孩', female: '女孩', unknown: '未填写' } as Record<string, string>)[gender || ''] || '未填写'
}

export function petTypeLabel(type: 'cat' | 'dog') {
  return type === 'cat' ? '猫' : '狗'
}

export function petAgeBandLabel(band: string) {
  return ({ junior: '幼年', adult: '成年', senior: '老年' } as Record<string, string>)[band] || band
}

export function neuteredLabel(value: boolean | null) {
  return value === true ? '已绝育' : value === false ? '未绝育' : '绝育情况未填写'
}

export function neuteredShortLabel(value: boolean | null) {
  return value === true ? '已绝育' : value === false ? '未绝育' : '未填写'
}

export function maskBirth(value: string) {
  const year = String(value).split('-')[0]
  return year ? `${year}-**-**` : '未填写'
}

export function childMeta(child: Pick<ChildProfileView, 'age_months' | 'gender'>) {
  return `${child.age_months} 个月 · ${genderLabel(child.gender)}`
}

export function petMeta(pet: Pick<PetProfileView, 'age_band' | 'neutered_flag'>) {
  return `${petAgeBandLabel(pet.age_band)} · ${neuteredLabel(pet.neutered_flag)}`
}

/**
 * 本地存储适配器（供各 store / 服务注入）。
 *
 * 为什么必须有这一层（缺陷：档案页「连接失败」）：
 * uni-app 的 H5 **生产构建**下，全局标识符 `uni` 并不承载完整 API
 * （`uni.getStorageSync` 为 undefined），只有 `import { uni } / 通过源码
 * import 的 uni 引用` 才是全量对象。把 `uni` 直接当作 `{ getStorageSync,
 * setStorageSync }` 适配器传入 store（如 `createProfileCurrentStore({ storage: uni })`）
 * 会在运行期抛 `TypeError: uni.getStorageSync is not a function`：
 * 该异常发生在页面 load() 的 try 中，被 catch 后渲染成
 * 「档案暂时无法打开 / 连接失败，请检查网络后重试。」——与网络无关的假故障。
 *
 * 因此统一约定：**任何 store / 服务的 storage 注入点都不得直接传 `uni`**，
 * 一律使用本模块导出的适配器（显式方法转发，语义与 uni.getStorageSync 一致）。
 */
export const uniStorage = {
  /**
   * 读取本地存储（键不存在返回空串，与 uni.getStorageSync 一致）。
   * @param key 存储键
   * @returns 存储值
   */
  getStorageSync(key: string): unknown {
    return uni.getStorageSync(key)
  },

  /**
   * 写入本地存储。
   * @param key 存储键
   * @param value 存储值（字符串/对象/数组/布尔/数字）
   */
  setStorageSync(key: string, value: unknown): void {
    uni.setStorageSync(key, value)
  },

  /**
   * 删除本地存储键。
   * @param key 存储键
   */
  removeStorageSync(key: string): void {
    uni.removeStorageSync(key)
  }
}

export type UniStorage = typeof uniStorage

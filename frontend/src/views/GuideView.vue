<script setup lang="ts">
const readOnly = import.meta.env.VITE_READ_ONLY_DEPLOYMENT === 'true'
</script>
<template>
  <section>
    <RouterLink to="/">← 返回首页</RouterLink>
    <h1>使用教程</h1>
    <p>从找到股票，到查看行情、理解均线和检查更新。</p>
    <div class="panel">
      <h2>1. 先打开一只有行情的股票</h2>
      <p v-if="readOnly">首页提供常用股票入口，实际采集范围由本环境的运维配置决定；可在详情核对已收录行情。</p>
      <p v-else>首页提供平安银行、贵州茅台、宁德时代和招商银行的入口。当前默认自动更新这 4 只股票。</p>
      <p>也可以在<RouterLink to="/stocks">股票搜索</RouterLink>输入代码或名称。能搜到股票不代表已经采集它的行情；上市日期和状态暂未收录时，不代表停牌或退市。</p>
      <RouterLink class="button-link" to="/stocks/600519.SH">用贵州茅台试一试 →</RouterLink>
    </div>
    <div class="panel">
      <h2>2. 选择日期，查看 K 线和成交量</h2>
      <p>进入详情后选择开始、结束日期，点击“查询行情”。拖动图表底部滑块可缩放时间范围，指向图形可查看当天数值；下方明细表保留精确价格。</p>
      <p>查询读取已有数据，不会临时联网补采。无数据时可更换日期或先查看首页中的 4 只股票；其他股票需由本机管理员补采。</p>
      <p>股价为当时实际交易价格（不复权），没有按后来的分红、送股调整历史价格。价格、成交金额单位为人民币元，成交量单位为股。</p>
    </div>
    <div class="panel">
      <h2>3. 理解 5 日、20 日和 60 日均线</h2>
      <p>均线是最近一段时间的平均收盘价。MA5、MA20、MA60 分别使用最近 5、20、60 个交易日，帮助观察不同时间范围的价格变化。</p>
      <p>“—”表示历史数据不足，暂时无法计算。均线由本项目根据已采集价格计算，不是上游直接给出的买卖建议。</p>
    </div>
    <div id="source-settings" class="panel">
      <p v-if="readOnly">当前为受邀只读环境。来源策略与采集范围由运维维护；本页的本地管理步骤只适用于开发环境。</p>
      <h2>4. 选择采集来源</h2>
      <template v-if="!readOnly">
      <p>在<RouterLink to="/source-settings">采集来源设置</RouterLink>选择“优先东方财富，失败时使用腾讯”，也可以固定使用其中一种来源。输入本地管理口令并点击“保存设置”。</p>
      <p>管理口令由本机管理员初始化。在运行本项目的电脑上打开终端，进入项目目录，执行下方命令读取管理口令，再粘贴到设置页。请勿把口令分享或提交到 Git。</p>
      <pre class="guide-command"><code>cat secrets/source-admin.token</code></pre>
      <p>保存后，下一次股票采集使用新策略，无需重启。已有行情不立即改变；看到“腾讯财经”仍可能是切换前保存的数据，或自动模式使用了备用来源。</p>
      </template>
    </div>
    <div class="panel">
      <h2>5. 检查自动更新</h2>
      <p>本地服务持续运行时，调度器在交易日上海时间 17:30 更新默认股票；启动时会检查最近已收盘交易日，已完成的任务会跳过。</p>
      <p>到<RouterLink to="/data-status">数据状态</RouterLink>查看任务是否成功。详情中的数据获取时间不是交易时间；重复获取相同数据时可能保留原时间。</p>
      <p>当前支持股票搜索、历史日线、成交量和基础均线。不提供实时行情、自动交易、收益保证或个性化买卖建议。</p>
    </div>
  </section>
</template>

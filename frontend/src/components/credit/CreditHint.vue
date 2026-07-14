<template>
  <span class="credit-hint" v-if="cost > 0">
    将扣除 {{ cost }} 积分
  </span>
</template>

<script setup>
defineProps({
  cost: { type: Number, required: true },
})
</script>

<style scoped>
.credit-hint {
  display: inline-block;
  margin-left: 8px;
  font-size: 12px;
  opacity: 0.8;
  color: inherit;
}
</style>

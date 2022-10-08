<template>
  <div class="h-screen w-screen">
    <slot />
  </div>
</template>

<style scoped>
div {
  background-color: hsla(147, 100%, 1%, 1);
  background-image: radial-gradient(at 99% 79%, hsla(289, 100%, 50%, 0.24) 0px, transparent 50%),
    radial-gradient(at 18% 100%, hsla(208, 47%, 24%, 0.71) 0px, transparent 50%),
    radial-gradient(at 0% 31%, hsla(289, 100%, 55%, 0.4) 0px, transparent 50%),
    radial-gradient(at 65% 0%, hsla(195, 70%, 53%, 0.4) 0px, transparent 50%);
}
</style>

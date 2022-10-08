<template>
  <div class="flex flex-col h-full w-full justify-center items-center">
    <div class="w-fit h-fit bg-white bg-opacity-10 flex flex-col rounded p-5">
      <h1 class="text-white font-bold text-3xl flex mb-5">Dune Admin Panel</h1>

      <label for="identifier" class="text-slate-300 text-sm mt-2">Nom d'utilisateur</label>
      <input type="text" name="identifier" class="rounded bg-opacity-10 mt-1" />

      <label for="password" class="text-slate-300 text-sm mt-2">Mot de passe</label>
      <input type="text" name="password" class="rounded bg-opacity-10 mt-1" />

      <button
        type="submit"
        class="text-white bg-white bg-opacity-10 rounded mt-5 h-8 hover:bg-slate-400 hover:bg-opacity-5 hover:shadow-md"
      >
        Se connecter
      </button>
    </div>
  </div>
</template>

<style></style>

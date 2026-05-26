module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
  ],
  plugins: ['vue', '@typescript-eslint'],
  ignorePatterns: ['dist', 'coverage', 'node_modules'],
  rules: {
    'vue/multi-word-component-names': 'off',
  },
}

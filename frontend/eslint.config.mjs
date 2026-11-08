import { FlatCompat } from "@eslint/eslintrc";
import { globalIgnores } from "eslint/config";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
});

const eslintConfig = [
  ...compat.config({
    extends: ["next/core-web-vitals", "next/typescript"],
  }),
  globalIgnores([".next/**", "node_modules/**", "next-env.d.ts"]),
];

export default eslintConfig;

/**
 * Deterministically unmount React trees before Vitest tears down jsdom.
 *
 * References:
 * - https://vitest.dev/config/setupfiles
 * - https://testing-library.com/docs/react-testing-library/setup/
 * - https://testing-library.com/docs/react-testing-library/api/#cleanup
 */
import {cleanup} from "@testing-library/react";
import {afterEach} from "vitest";

afterEach(() => cleanup());

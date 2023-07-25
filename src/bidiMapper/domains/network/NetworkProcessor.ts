/**
 * Copyright 2023 Google LLC.
 * Copyright (c) Microsoft Corporation.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import {
  type Network,
  type EmptyResult,
  UnknownCommandException,
  NoSuchInterceptException,
} from '../../../protocol/protocol.js';
import {uuidv4} from '../../../utils/uuid.js';

import type {NetworkStorage} from './NetworkStorage.js';

export class NetworkProcessor {
  readonly #networkStorage: NetworkStorage;

  constructor(networkStorage: NetworkStorage) {
    this.#networkStorage = networkStorage;
  }

  addIntercept(
    params: Network.AddInterceptParameters
  ): Network.AddInterceptResult {
    const intercept = uuidv4();

    const urlPatterns: string[] = params.urlPatterns ?? [];
    const parsedPatterns: string[] = [];
    for (const urlPattern of urlPatterns) {
      const parsed = urlPattern; // TODO: Parse the pattern.
      parsedPatterns.push(parsed);
    }

    this.#networkStorage.interceptMap.set(intercept, {
      urlPatterns: parsedPatterns,
      phases: params.phases,
    });

    return {
      intercept,
    };
  }

  continueRequest(_params: Network.ContinueRequestParameters): EmptyResult {
    throw new UnknownCommandException('Not implemented yet.');
  }

  continueResponse(_params: Network.ContinueResponseParameters): EmptyResult {
    throw new UnknownCommandException('Not implemented yet.');
  }

  continueWithAuth(_params: Network.ContinueWithAuthParameters): EmptyResult {
    throw new UnknownCommandException('Not implemented yet.');
  }

  failRequest(_params: Network.FailRequestParameters): EmptyResult {
    throw new UnknownCommandException('Not implemented yet.');
  }

  provideResponse(_params: Network.ProvideResponseParameters): EmptyResult {
    throw new UnknownCommandException('Not implemented yet.');
  }

  removeIntercept(params: Network.RemoveInterceptParameters): EmptyResult {
    const intercept = params.intercept;
    const interceptMap = this.#networkStorage.interceptMap;

    if (!interceptMap.has(intercept)) {
      throw new NoSuchInterceptException(
        `Intercept ${intercept} does not exist.`
      );
    }

    interceptMap.delete(intercept);

    return {};
  }
}

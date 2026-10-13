import { z } from 'zod';
import { schemas } from '../api/schemas';
export const voiceMessage=z.discriminatedUnion('type',[
  z.object({type:z.literal('ready'),revision:z.number().int()}),
  z.object({type:z.literal('fallback'),provider:z.enum(['parakeet','openai']),reason:z.enum(['quota','selected'])}),
  z.object({type:z.literal('interrupt'),revision:z.number().int()}),
  z.object({type:z.literal('partial'),text:z.string()}),
  z.object({type:z.literal('committed'),event:schemas.Event}),
  z.object({type:z.literal('reply'),event:schemas.Event,revision:z.number().int()}),
  z.object({type:z.literal('state'),state:z.enum(['thinking','listening']),revision:z.number().int()}),
  z.object({type:z.literal('look'),revision:z.number().int()}),
  z.object({type:z.literal('error'),message:z.string(),fatal:z.boolean()}),
]);

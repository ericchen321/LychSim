// Weichao Qiu @ 2017
/** Low level API to read texture from UE4 */
#pragma once

#include "CoreMinimal.h"
#include "Runtime/Engine/Classes/Engine/TextureRenderTarget2D.h"

LYCHSIM_API bool ReadTextureRenderTarget(UTextureRenderTarget2D* RenderTarget, TArray<FColor>& ImageData, int& Width, int& Height);

/** Read texture from UE4 and keep the texture size */
LYCHSIM_API bool FastReadTexture2DAsync(FTexture2DRHIRef Texture2D, TFunction<void(FColor*, int32, int32)> Callback);

/** Read texture from UE4 and resize to expected size */
// LYCHSIM_API bool ResizeFastReadTexture2DAsync(FTexture2DRHIRef Texture2D, int TargetWidth, int TargetHeight, TFunction<void(FColor*, int32, int32)> Callback);

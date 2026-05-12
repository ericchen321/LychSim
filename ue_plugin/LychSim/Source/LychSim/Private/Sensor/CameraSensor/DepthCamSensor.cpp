// Weichao Qiu @ 2017
#include "DepthCamSensor.h"
#include "AnnotationCamSensor.h"
#include "TextureResource.h"
#include "Runtime/Core/Public/Async/ParallelFor.h"

UDepthCamSensor::UDepthCamSensor(const FObjectInitializer& ObjectInitializer) :
	Super(ObjectInitializer)
{
	// this->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
	this->CaptureSource = ESceneCaptureSource::SCS_SceneDepth;
	bIgnoreTransparentObjects = false;
}

void UDepthCamSensor::InitTextureTarget(int filmWidth, int filmHeight)
{
	EPixelFormat PixelFormat = EPixelFormat::PF_FloatRGBA;
	bool bUseLinearGamma = true;
 	TextureTarget->InitCustomFormat(filmWidth, filmHeight, EPixelFormat::PF_FloatRGBA, bUseLinearGamma);
}

void UDepthCamSensor::CaptureDepth(TArray<float>& DepthData, int& Width, int& Height)
{
	if (!bIgnoreTransparentObjects)
	{
		auto PrevMode = this->PrimitiveRenderMode;
		FEngineShowFlags PrevFlags = this->ShowFlags;
		TArray<TWeakObjectPtr<UPrimitiveComponent>> PrevShowOnly = this->ShowOnlyComponents;

		TArray<TWeakObjectPtr<UPrimitiveComponent>> ComponentList;
		UAnnotationCamSensor::GetAnnotationComponents(this->GetWorld(), ComponentList);
		this->ShowOnlyComponents = ComponentList;
		this->PrimitiveRenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
		this->ShowFlags.SetMaterials(false); // This will make annotation component visible

		if (CheckTextureTarget())
		{
			this->CaptureScene();
			FlushRenderingCommands();
		}

		this->ShowOnlyComponents = MoveTemp(PrevShowOnly);
		this->PrimitiveRenderMode = PrevMode;
		this->ShowFlags = PrevFlags;
	}
	else
	{
		if (!CheckTextureTarget()) return;
		this->CaptureScene();
		FlushRenderingCommands();
	}

	Width = this->TextureTarget->SizeX, Height = TextureTarget->SizeY;
	DepthData.AddZeroed(Width * Height); // or AddUninitialized(FloatColorDepthData.Num());
	FTextureRenderTargetResource* RenderTargetResource = this->TextureTarget->GameThread_GetRenderTargetResource();
	TArray<FFloat16Color> FloatColorDepthData;
	RenderTargetResource->ReadFloat16Pixels(FloatColorDepthData);

    ParallelFor(FloatColorDepthData.Num(), [&](int32 i)
    {
        if (i >= 0 && i < FloatColorDepthData.Num() && i < DepthData.Num())
        {
            FFloat16Color& FloatColor = FloatColorDepthData[i];
            DepthData[i] = FloatColor.R;
        }
    });
}

void UDepthCamSensor::CaptureZBuffer(
    TArray<float>& DepthData, const TArray<AActor*>& Actors, int& Width, int& Height)
{
    if (Actors.Num() == 0 || !CheckTextureTarget())
	{
		DepthData.Reset();
		return;
	}

    const auto PrevMode = this->PrimitiveRenderMode;
    const auto PrevSrc = this->CaptureSource;
    const bool PrevIgn = this->bIgnoreTransparentObjects;

    this->PrimitiveRenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
    this->CaptureSource = ESceneCaptureSource::SCS_SceneDepth;
    this->bIgnoreTransparentObjects = true;

    Width = this->TextureTarget->SizeX; Height = this->TextureTarget->SizeY;
    DepthData.Reset();
	DepthData.AddZeroed((int64)Actors.Num() * Width * Height);

    TArray<float> CurrentDepthData;
	CurrentDepthData.Reserve((int64)Width * Height);

    for (int32 i = 0; i < Actors.Num(); ++i)
    {
        AActor* A = Actors[i];
        if (!IsValid(A)) continue;

        this->ClearShowOnlyComponents();
        this->ShowOnlyActorComponents(A, /*bIncludeChildren=*/true);

        this->MarkRenderStateDirty();
        FlushRenderingCommands();
        this->CaptureScene();
        FlushRenderingCommands();

        CurrentDepthData.Reset();
        this->CaptureDepth(CurrentDepthData, Width, Height);
        if (CurrentDepthData.Num() == Width * Height)
        {
            float* Dst = DepthData.GetData() + (int64)i * Width * Height;
            FMemory::Memcpy(Dst, CurrentDepthData.GetData(), sizeof(float) * Width * Height);
        }
    }

    this->ClearShowOnlyComponents();
    this->PrimitiveRenderMode = PrevMode;
    this->CaptureSource = PrevSrc;
    this->bIgnoreTransparentObjects = PrevIgn;
    this->MarkRenderStateDirty();
    FlushRenderingCommands();
}

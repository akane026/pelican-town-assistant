# 精简图文待审清单

快照 `0f47248587aed45b1fc0887be608e3bd8ad429f79e363e841c4b828dcd7b2ac0`。以下均待用户审核；自动 matched 不是人审通过。

在工作台“建库审阅”中可搜索 ID，查看原图、区域坐标、完整原文与模型理由，输入审核依据后决定批准/拒绝/保留。

## 1. entity:Potato
记录：`alignment:9b48dd24650c4349d03f1ec0133b`；自动状态：matched；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.16875,0.45,0.83125,0.83125]]
The region contains a large brown oval shape with spots, explicitly described as a potato in the visual description. This matches the entity 'Potato'.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `image[110]`。
> 

用户结论：待填写；依据：待填写。

## 2. relation:8d342fa859bdbc4bb95fb7f9b9ab
记录：`alignment:26a63f9216291d7a1fd94174651f`；自动状态：matched；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.16875,0.45,0.83125,0.83125]]
The region depicts a Potato. Since the provided source quotes and relations list 'Potato' as a requirement for the 'Spring Crops Bundle', and this image illustrates the bundle components, this region illustrates the subject 'Potato' of the relation relation:8d342fa859bdbc4bb95fb7f9b9ab.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `table[11]`。
> Spring Crops Bundle Parsnip Spring Crops Green Bean Spring Crops Cauliflower Spring Crops Potato Spring Crops Reward: Speed-Gro (20)

用户结论：待填写；依据：待填写。

## 3. entity:Green_Bean
记录：`alignment:728e18d067315252f1a49c7bfc07`；自动状态：ambiguous；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.44375,0.16875,0.80625,0.85]]
The visual description identifies this region as 'leafy_greens' (green leafy vegetable with curved stem). In the context of the 'Spring Crops Bundle' (Parsnip, Green Bean, Cauliflower, Potato), 'leafy_greens' visually corresponds to the Green Bean (often depicted as a pod with stem in this game's style) or potentially the Cauliflower leaves. Given the specific 'leafy' description vs 'pod' shape, it is ambiguous but likely represents the Green Bean due to the bean-like curve.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `image[110]`。
> 

用户结论：待填写；依据：待填写。

## 4. relation:f18cd274d6501ad163e9d7ea54c1
记录：`alignment:f190edd80a4f4fd57dde8435cd70`；自动状态：ambiguous；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.44375,0.16875,0.80625,0.85]]
This region depicts a green leafy/curved vegetable. It is mapped ambiguously to the Green Bean entity (and thus its relation), as it could potentially be Cauliflower leaves or another item not listed, but fits the visual of a Green Bean in this bundle context.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `table[11]`。
> Spring Crops Bundle Parsnip Spring Crops Green Bean Spring Crops Cauliflower Spring Crops Potato Spring Crops Reward: Speed-Gro (20)

用户结论：待填写；依据：待填写。

## 5. entity:Parsnip
记录：`alignment:20c5fa53c65cf3c1cd42c6b799b2`；自动状态：ambiguous；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.2375,0.2375,0.55625,0.4875]]
The visual description identifies an 'Orange tapered root vegetable'. While described as a carrot, in Stardew Valley's Spring Crops Bundle, the root vegetable is a Parsnip (which can appear orange/tan and tapered). The provided entities list does not include 'Carrot', only 'Parsnip'. Thus, this region is ambiguous between the visual description (carrot) and the available entity (Parsnip).

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `image[110]`。
> 

用户结论：待填写；依据：待填写。

## 6. relation:8f944c4ba97f3864d24cf58b639d
记录：`alignment:c1225001d94d0bd508289aba374c`；自动状态：ambiguous；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.2375,0.2375,0.55625,0.4875]]
Maps ambiguously to the Parsnip relation because the visual object (orange root) is described as a carrot but must map to one of the supplied entities (Parsnip) to support the bundle relation, creating a discrepancy between visual text and entity list.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `table[11]`。
> Spring Crops Bundle Parsnip Spring Crops Green Bean Spring Crops Cauliflower Spring Crops Potato Spring Crops Reward: Speed-Gro (20)

用户结论：待填写；依据：待填写。

## 7. entity:Spring_Crops_Bundle
记录：`alignment:ef09500251bac54b7a73f339977c`；自动状态：matched；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.16875,0.45,0.83125,0.83125],[0.2375,0.2375,0.55625,0.4875],[0.44375,0.16875,0.80625,0.85]]
The collection of regions (Potato, Root Vegetable, Greens) corresponds to the components of the 'Spring Crops Bundle' as defined in the source quotes and relations. Together they depict the bundle.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `image[110]`。
> 

用户结论：待填写；依据：待填写。

## 8. relation:8d342fa859bdbc4bb95fb7f9b9ab
记录：`alignment:d01802273ae3bfe5650464afcea0`；自动状态：ambiguous；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.16875,0.45,0.83125,0.83125],[0.2375,0.2375,0.55625,0.4875],[0.44375,0.16875,0.80625,0.85]]
The bundle depiction implicitly supports the 'BUNDLE_REQUIREMENT' relations. This specific relation (Potato) is strongly supported by the Potato region but is part of the whole.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `table[11]`。
> Spring Crops Bundle Parsnip Spring Crops Green Bean Spring Crops Cauliflower Spring Crops Potato Spring Crops Reward: Speed-Gro (20)

用户结论：待填写；依据：待填写。

## 9. relation:658d36fbce3be4eeea8ec2663b45
记录：`alignment:2a704e6c39e3270c82a99dda5cea`；自动状态：rejected；方法：compound_mllm_alignment/v1

![原始 Wiki 图像](../../data/raw/wiki_assets/26f760a950d7443ced99f1482424ce8d550467a0f23d85b01d137a5606735632.png)
区域：[[0.2375,0.2375,0.55625,0.4875]]
No region clearly depicts 'Cauliflower'. The orange vegetable is identified as a root (Parsnip/Carrot), and the green vegetable is identified as leafy greens (Green Bean). Cauliflower is typically white with a green crown, which is not explicitly described in the object regions.

来源：[ Bundles / 195448 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Bundles&oldid=195448)；定位 `table[11]`。
> Spring Crops Bundle Parsnip Spring Crops Green Bean Spring Crops Cauliflower Spring Crops Potato Spring Crops Reward: Speed-Gro (20)

用户结论：待填写；依据：待填写。

## 10. entity:Parsnip@ac91b3ec:stage:1
记录：`alignment:05d2d909c2be6c4e18d6e2e7e987`；自动状态：matched；方法：structural_anchor_with_pixel_check/v1

![原始 Wiki 图像](../../verification/data/assets/cda9cc5a5b35b50f6b8e1f7596cad602246faa3c92b55e7610d18830586400ad.png)
区域：[[0,0,1,1]]
Structural candidate retained; pixel decoding validated, semantic identity not independently validated.

来源：[ Parsnip / 191123 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Parsnip&oldid=191123)；定位 `table[10]`。
> Stage 1 Stage 2 Stage 3 Stage 4 Harvest 1 Day 1 Day 1 Day 1 Day Total: 4 Days

用户结论：待填写；依据：待填写。

## 11. entity:Kale
记录：`fact:95557b835d4a60a63342ee7b6a82`；自动状态：candidate；方法：table_structure

候选值：110 g

来源：[ Kale / 192520 ](https://stardewvalleywiki.com/mediawiki/index.php?title=Kale&oldid=192520)；定位 `table[2]/row[2]/cell[0]`。
> 110g 137g 165g 220g

用户结论：待填写；依据：待填写。


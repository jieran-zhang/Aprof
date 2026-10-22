        if (aprof::Enabled()) {
            {
                constexpr size_t stride = 512;
                constexpr uint64_t aprofChunkElements = @CHUNK_ELEMENTS@;
                static_assert(sizeof(ForeachAddcdivTilingData) <= stride, "tiling exceeds prepared stride");
                size_t totalBytes = 0, chunkCount = 0;
                for (auto n : lengths) { totalBytes += (static_cast<size_t>(n)*elemBytes+511)/512*512; chunkCount += (n+aprofChunkElements-1)/aprofChunkElements; }
                aprof::Buffer p1(totalBytes), p2(totalBytes), p3(totalBytes), py(totalBytes), pt(chunkCount*stride);
                std::vector<ForeachAddcdivTilingData> preparedTilings;
                std::vector<size_t> offsets, chunkBytes;
                size_t offset = 0;
                for (auto tensorLength : lengths) {
                    for (uint64_t off=0; off<tensorLength; off+=aprofChunkElements) {
                        const uint64_t n = std::min<uint64_t>(aprofChunkElements, tensorLength-off);
                        const size_t bytes = static_cast<size_t>(n)*elemBytes;
                        std::vector<uint8_t> h1(bytes), h2(bytes), h3(bytes);
                        ReadExact(f1, h1.data(), bytes, "x1"); ReadExact(f2, h2.data(), bytes, "x2"); ReadExact(f3, h3.data(), bytes, "x3");
                        Check(aclrtMemcpy(p1.at(offset), bytes, h1.data(), bytes, ACL_MEMCPY_HOST_TO_DEVICE), "prepare x1");
                        Check(aclrtMemcpy(p2.at(offset), bytes, h2.data(), bytes, ACL_MEMCPY_HOST_TO_DEVICE), "prepare x2");
                        Check(aclrtMemcpy(p3.at(offset), bytes, h3.data(), bytes, ACL_MEMCPY_HOST_TO_DEVICE), "prepare x3");
                        auto tiling = ComputeForeachAddcdivTiling(n, dtype, cores, scalar);
                        Check(aclrtMemcpy(pt.at(preparedTilings.size()*stride), stride, &tiling, sizeof(tiling), ACL_MEMCPY_HOST_TO_DEVICE), "prepare tiling");
                        preparedTilings.push_back(tiling); offsets.push_back(offset); chunkBytes.push_back(bytes); offset += (bytes+511)/512*512;
                    }
                }
                auto launch = [&]() {
                    for (size_t i=0; i<preparedTilings.size(); ++i)
                        foreach_addcdiv_scalar_kernel<<<preparedTilings[i].blockNum, nullptr, stream>>>(p1.at(offsets[i]), p2.at(offsets[i]), p3.at(offsets[i]), py.at(offsets[i]), pt.at(i*stride));
                };
                aprof::Run(stream, device, "foreach_addcdiv_scalar", preparedTilings.size(), launch);
                for (size_t i=0; i<preparedTilings.size(); ++i) {
                    std::vector<uint8_t> output(chunkBytes[i]);
                    Check(aclrtMemcpy(output.data(), output.size(), py.at(offsets[i]), output.size(), ACL_MEMCPY_DEVICE_TO_HOST), "prepared output");
                    if (!fo.write(reinterpret_cast<const char *>(output.data()), output.size())) throw std::runtime_error("write prepared output failed");
                }
            }
            aclrtDestroyStream(stream); stream=nullptr; aclrtResetDevice(device); aclFinalize();
            return 0;
        }

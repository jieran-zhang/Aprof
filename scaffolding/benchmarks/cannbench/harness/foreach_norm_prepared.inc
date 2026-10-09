        if (aprof::Enabled()) {
            {
                constexpr size_t stride = 512;
                static_assert(sizeof(ForeachNormTilingData) <= stride, "tiling exceeds prepared stride");
                size_t totalBytes = 0;
                for (auto n : lengths) totalBytes += (static_cast<size_t>(n) * elemBytes + 511)/512*512;
                aprof::Buffer px(totalBytes), pt(lengths.size()*stride), py(lengths.size()*32), pp(static_cast<size_t>(cores)*32);
                std::vector<ForeachNormTilingData> preparedTilings;
                std::vector<size_t> offsets;
                size_t offset = 0;
                for (auto n : lengths) {
                    const size_t bytes = static_cast<size_t>(n)*elemBytes;
                    std::vector<uint8_t> input(bytes);
                    ReadExact(fi, input.data(), bytes);
                    Check(aclrtMemcpy(px.at(offset), bytes, input.data(), bytes, ACL_MEMCPY_HOST_TO_DEVICE), "prepare x");
                    auto tiling = ComputeForeachNormTiling(n, dtype, cores, scalar);
                    Check(aclrtMemcpy(pt.at(preparedTilings.size()*stride), stride, &tiling, sizeof(tiling), ACL_MEMCPY_HOST_TO_DEVICE), "prepare tiling");
                    preparedTilings.push_back(tiling); offsets.push_back(offset); offset += (bytes+511)/512*512;
                }
                auto launch = [&]() {
                    for (size_t i=0; i<lengths.size(); ++i) {
                        foreach_norm_partial_kernel<<<preparedTilings[i].blockNum, nullptr, stream>>>(px.at(offsets[i]), pp.at(), pt.at(i*stride));
                        foreach_norm_finalize_kernel<<<1, nullptr, stream>>>(pp.at(), py.at(i*32), pt.at(i*stride));
                    }
                };
                aprof::Run(stream, device, "foreach_norm", 2*lengths.size(), launch);
                for (size_t i=0; i<lengths.size(); ++i) {
                    std::vector<uint8_t> output(elemBytes);
                    Check(aclrtMemcpy(output.data(), elemBytes, py.at(i*32), elemBytes, ACL_MEMCPY_DEVICE_TO_HOST), "prepared output");
                    if (!fo.write(reinterpret_cast<const char *>(output.data()), elemBytes)) throw std::runtime_error("write prepared output failed");
                }
            }
            aclrtDestroyStream(stream); stream=nullptr; aclrtResetDevice(device); aclFinalize();
            return 0;
        }
